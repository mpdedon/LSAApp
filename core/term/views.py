from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import TermForm
from ..models import Term

class TermListView(View):
    template_name = 'term/term_list.html'

    def get(self, request):
        terms = Term.objects.all()
        return render(request, self.template_name, {'terms': terms})

class TermDetailView(View):
    template_name = 'term/term_detail.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        return render(request, self.template_name, {'term': term})

class TermCreateView(View):
    template_name = 'term/term_form.html'

    def get(self, request):
        form = TermForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = TermForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('term_list')
        return render(request, self.template_name, {'form': form})

class TermUpdateView(View):
    template_name = 'term/term_form.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        form = TermForm(instance=term)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        form = TermForm(request.POST, instance=term)
        if form.is_valid():
            form.save()
            return redirect('term_list')
        return render(request, self.template_name, {'form': form})

class TermDeleteView(View):
    template_name = 'term/term_confirm_delete.html'

    def get(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        return render(request, self.template_name, {'term': term})

    def post(self, request, pk):
        term = get_object_or_404(Term, pk=pk)
        term.delete()
        return redirect('term_list')
