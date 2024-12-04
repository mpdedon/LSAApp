from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import ExpenseForm
from ..models import Expense

class ExpenseListView(View):
    template_name = 'expenses/expense_list.html'

    def get(self, request):
        expenses = Expense.objects.all()
        return render(request, self.template_name, {'expenses': expenses})

class ExpenseDetailView(View):
    template_name = 'expenses/expense_detail.html'

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        return render(request, self.template_name, {'expense': expense})

class ExpenseCreateView(View):
    template_name = 'expenses/expense_form.html'

    def get(self, request):
        form = ExpenseForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('expense_list')
        return render(request, self.template_name, {'form': form})

class ExpenseUpdateView(View):
    template_name = 'expenses/expense_form.html'

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseForm(instance=expense)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            return redirect('expense_list')
        return render(request, self.template_name, {'form': form})

class ExpenseDeleteView(View):
    template_name = 'expenses/expense_confirm_delete.html'

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        return render(request, self.template_name, {'expense': expense})

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        expense.delete()
        return redirect('expense_list')
