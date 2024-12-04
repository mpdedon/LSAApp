from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import SessionForm
from ..models import Session

class SessionListView(View):
    template_name = 'session/session_list.html'

    def get(self, request):
        sessions = Session.objects.all()
        return render(request, self.template_name, {'sessions': sessions})

class SessionDetailView(View):
    template_name = 'session/session_detail.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        return render(request, self.template_name, {'session': session})

class SessionCreateView(View):
    template_name = 'session/session_form.html'

    def get(self, request):
        form = SessionForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('session_list')
        return render(request, self.template_name, {'form': form})

class SessionUpdateView(View):
    template_name = 'session/session_form.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        form = SessionForm(instance=session)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('session_list')
        return render(request, self.template_name, {'form': form})

class SessionDeleteView(View):
    template_name = 'session/session_confirm_delete.html'

    def get(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        return render(request, self.template_name, {'session': session})

    def post(self, request, pk):
        session = get_object_or_404(Session, pk=pk)
        session.delete()
        return redirect('session_list')
