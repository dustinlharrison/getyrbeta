import datetime

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import UpdateView, ListView, \
    CreateView, DeleteView, DetailView, FormView, View
from django.utils import timezone
from django.contrib.auth import authenticate
from django.http import JsonResponse, Http404

from .models import Trip, TripLocation, TripMember, ItemNotification

from account_info.models import User

from .forms import TripForm, LocationForm, SearchForm, TripMemberForm


class LoginRequiredMixin:
    def get(self, request, *args, **kwargs):
        if request.user and request.user.is_authenticated():
            return super(LoginRequiredMixin, self).get(
                self, request, *args, **kwargs)
        else:
            redirect_path = reverse('authentication:login')
            redirect_next = '?next=' + request.path
            return redirect(redirect_path + redirect_next)

    def post(self, request, *args, **kwargs):
        if request.user and request.user.is_authenticated():
            return super(LoginRequiredMixin, self).post(
                self, request, *args, **kwargs)
        else:
            redirect_path = reverse('authentication:login')
            redirect_next = '?next=' + request.path
            return redirect(redirect_path + redirect_next)


class LocationGeneralMixin:
    """
    This mixin is used by all views for the Location model.
    """
    model = TripLocation

    # set_instance_variables() is a callable located in the primary class
    # description. The output is used by get_context_data()
    def get(self, request, *args, **kwargs):
        self.set_instance_variables(**kwargs)
        return super(LocationGeneralMixin, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.set_instance_variables(**kwargs)
        return super(LocationGeneralMixin, self).post(request, *args, **kwargs)

    # The context data is used by the template
    def get_context_data(self, **kwargs):
        context = super(LocationGeneralMixin, self).get_context_data(**kwargs)
        context['page_title'] = self.page_title
        context['submit_button_title'] = self.submit_button_title
        context['cancel_button_path'] = 'trips:trip_detail'
        context['trip_id'] = self.kwargs.get('trip_id')
        return context

    def get_success_url(self):
        return reverse('trips:trip_detail', args=(self.kwargs.get('trip_id'),))

class LocationFormMixin:
    """
    This mixin is used by all views for the Location model that include a
    form. The view will receive a location_type in the url (trailhead,
    objective, or camp). The view converts this to a two character code
    through a model method. The get_form_kwargs receives the two character code
    and calls another model method, passing the appropriate argument, and
    receives a list of date choices (prefixed with either 'Day' or 'Night'
    according to the location_type.)
    """
    model = TripLocation
    template_name = 'trips/location.html'
    form_class = LocationForm

    def get_form_kwargs(self):
        """
        Adds a tuple of choices for the date field to the form kwargs.
        """
        kwargs = super(LocationFormMixin, self).get_form_kwargs()
        kwargs['location_type'] = self.kwargs.get('location_type')
        if kwargs['location_type'] == TripLocation.CAMP:
            date_type = 'night'
        else:
            date_type = 'day'
        date_list = Trip.objects.get(pk=self.kwargs.get(
            'trip_id')).get_date_choices(date_type)
        choices = []
        for item in date_list:
            choices.append((item, item))
        kwargs['choices'] = tuple(choices)

        return kwargs

class TripListView(LoginRequiredMixin, ListView):
    model = Trip
    template_name = 'trips/index.html'

    def get_queryset(self):
        queryset = self.request.user.trip_set.all()
        return queryset

    def get_context_data(self, **kwargs):
        context = super(TripListView, self).get_context_data(**kwargs)
        context['upcoming_trip_list'] = self.object_list.filter(
            start_date__gte=timezone.now()).order_by('start_date')
        context['past_trip_list'] = self.object_list.filter(
            start_date__lt=timezone.now()).order_by('start_date')
        return context

class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = 'trips/detail.html'

    def get_context_data(self, **kwargs):
        context = super(TripDetailView, self).get_context_data(**kwargs)
        trip = self.get_object()
        context['page_title'] = trip.title
        if trip.number_nights > 0:
            context['end_date'] = trip.start_date + datetime.timedelta(
                days=trip.number_nights)

        context['trailhead'] = trip.get_trailhead()
        context['endpoint'] = trip.get_endpoint()

        context['objective_dict'] = trip.get_location_context(
            TripLocation.OBJECTIVE)
        context['camp_dict'] = trip.get_location_context(TripLocation.CAMP)
        return context

class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    template_name = 'trips/create.html'
    form_class = TripForm

    def get_context_data(self, **kwargs):
        context = super(TripCreateView, self).get_context_data(**kwargs)
        context['page_title'] = 'Start a new trip'
        context['submit_button_title'] = 'Save Trip'
        context['cancel_button_path'] = 'trips:trip_list'
        return context

    def form_valid(self, form):
        """
        Set values for the form based on data passed by AJAX request and
        on intended functionality
        """
        response = super(TripCreateView, self).form_valid(form)
        TripMember.objects.create(
            organizer=True,
            accept_reqd=False,
            trip=self.object,
            member=self.request.user,
            email=self.request.user.email
        )
        return response

    def get_success_url(self):
        return reverse('trips:trip_detail', args=(self.object.id,))

class LocationCreateView(LoginRequiredMixin, LocationGeneralMixin,
    LocationFormMixin, CreateView):
    def set_instance_variables(self, **kwargs):
        url_location_type = self.kwargs.get('location_type').lower()
        try:
            self.kwargs['location_type'] = TripLocation.LOCATION_TYPE[
                url_location_type]
            self.page_title = 'Enter a new ' + url_location_type + ' location'
            self.submit_button_title = 'Save ' + url_location_type.capitalize()
        except KeyError:
            raise Http404('Invalid location type: ' + url_location_type)

    def get_initial(self):
        trip = get_object_or_404(Trip, pk=self.kwargs.get('trip_id'))
        location_type = self.kwargs.get('location_type')
        return {
            'trip': trip,
            'location_type': location_type,
            'date': trip.get_date_choices()[0]
        }

class LocationEditView(LoginRequiredMixin, LocationGeneralMixin,
    LocationFormMixin, UpdateView):
    def set_instance_variables(self, **kwargs):
        url_location_type = self.kwargs.get('location_type').lower()
        try:
            self.kwargs['location_type'] = TripLocation.LOCATION_TYPE[
                url_location_type]
            self.page_title = 'Edit ' + url_location_type + ' details'
            self.submit_button_title = 'Save ' + url_location_type.capitalize()
        except KeyError:
            raise Http404('Invalid location type: ' + url_location_type)

class LocationDeleteView(LoginRequiredMixin, LocationGeneralMixin, DeleteView):
    template_name = 'trips/delete.html'
    context_object_name = 'triplocation'

    def set_instance_variables(self, **kwargs):
        url_location_type = self.kwargs.get('location_type').lower()
        try:
            # setting 'location_type' ensures a valid URL is entered
            self.kwargs['location_type'] = TripLocation.LOCATION_TYPE[
                url_location_type]
            self.page_title = 'Delete ' + url_location_type
            self.submit_button_title = 'Delete ' + url_location_type.capitalize()
        except KeyError:
            raise Http404('Invalid location type: ' + url_location_type)

class TripMemberListView(LoginRequiredMixin, FormView):
    model = TripMember
    template_name = 'trips/members.html'
    queryset = TripMember.objects.all()
    form_class = SearchForm

    def get_context_data(self, **kwargs):
        context = super(TripMemberListView, self).get_context_data(**kwargs)
        trip = Trip.objects.get(pk=self.kwargs['pk'])
        context['trip'] = trip
        context['pending_members'] = self.queryset.filter(
            trip=trip, accept_reqd=True).order_by('email')
        context['current_members'] = self.queryset.filter(
            trip=trip, accept_reqd=False).order_by('email')
        return context

class CheckUserExistsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        email = request.GET.get('email')
        trip = Trip.objects.get(pk=int(request.GET.get('trip_id')))
        if User.objects.filter(email__iexact=email).exists() and not \
        TripMember.objects.filter(email__iexact=email, trip=trip).exists():
            status = 'valid'
        elif TripMember.objects.filter(email__iexact=email).exists():
            status = 'current_member'
        else:
            status = 'non_user'

        data = {'status': status}
        return JsonResponse(data)

class AddTripMemberView(LoginRequiredMixin, CreateView):
    model = TripMember
    form_class = TripMemberForm
    success_url = "#"

    def post(self, request, *args, **kwargs):
        self.kwargs['trip_id'] = request.POST.get('trip_id')
        self.kwargs['email'] = request.POST.get('email')
        return super(AddTripMemberView, self).post(request, *args, **kwargs)

    def form_invalid(self, form):
        response = super(AddTripMemberView, self).form_invalid(form)
        return JsonResponse(form.errors, status=400)

    def form_valid(self, form):
        """
        Set values for the form based on data passed by AJAX request and
        on intended functionality
        """
        f = form.save(commit=False)
        f.trip_id = int(self.kwargs.get('trip_id'))
        f.member_id = get_object_or_404(
            User, email=self.kwargs.get('email')).id
        f.organizer = True
        f.accept_reqd = True
        f.email = self.kwargs.get('email')
        f.save()
        response = super(AddTripMemberView, self).form_valid(form)
        data = {
            'email': self.object.member.email
        }
        if self.object.member.preferred_name:
            data['preferred_name'] = self.object.member.preferred_name
        else:
            data['preferred_name'] = ''

        return JsonResponse(data)

class NotificationListView(LoginRequiredMixin, ListView):
    model = TripMember
    template_name = 'trips/notifications.html'
    context_object_name = 'trip_notifications'

    def get_queryset(self):
        # gets all trip notifications for logged in user
        queryset = super(NotificationListView, self).get_queryset()
        return queryset.filter(member=self.request.user, accept_reqd=True)

    def get_context_data(self, **kwargs):
        # context already has 'trip_notifications' through standard ListView
        # add 'item_notifications' to context
        context = super(NotificationListView, self).get_context_data(**kwargs)
        context['item_notifications'] = ItemNotification.objects.filter(owner=self.request.user)
        context['user_id'] = self.request.user
        return context

class UpdateTripMemberView(LoginRequiredMixin, UpdateView):
    model = TripMember
    form_class = TripMemberForm
    success_url = "#"

    def post(self, request, *args, **kwargs):
        self.kwargs['trip_id'] = request.POST.get('trip_id')
        return super(UpdateTripMemberView, self).post(request, *args, **kwargs)

    def get_object(self):
        obj = get_object_or_404(
            TripMember,
            member_id=self.request.user.id,
            trip_id=int(self.kwargs.get('trip_id'))
        )
        return obj

    def form_invalid(self, form):
        response = super(UpdateTripMemberView, self).form_invalid(form)
        return JsonResponse(form.errors, status=400)

    def form_valid(self, form):
        """
        Set values for the form based on data passed by AJAX request and
        on intended functionality
        """
        f = form.save(commit=False)
        f.accept_reqd = False
        f.save()
        super(UpdateTripMemberView, self).form_valid(form)
        data = {}
        return JsonResponse(data)

class DeleteTripMemberView(LoginRequiredMixin, DeleteView):
    model = TripMember
    success_url = "#"

    def post(self, request, *args, **kwargs):
        self.kwargs['trip_id'] = request.POST.get('trip_id')
        super(DeleteTripMemberView, self).post(request, *args, **kwargs)
        data = {}
        return JsonResponse(data)

    def get_object(self):
        obj = get_object_or_404(
            TripMember,
            member_id=self.request.user.id,
            trip_id=int(self.kwargs.get('trip_id'))
        )
        return obj
