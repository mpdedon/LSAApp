from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import FinancialRecordForm
from ..models import FinancialRecord

class FinancialRecordListView(View):
    template_name = 'financial_record/financial_record_list.html'

    def get(self, request):
        financial_records = FinancialRecord.objects.all()
        return render(request, self.template_name, {'financial_records': financial_records})

class FinancialRecordDetailView(View):
    template_name = 'financial_record/financial_record_detail.html'

    def get(self, request, pk):
        financial_record = get_object_or_404(FinancialRecord, pk=pk)
        return render(request, self.template_name, {'financial_record': financial_record})

class FinancialRecordCreateView(View):
    template_name = 'financial_record/financial_record_form.html'

    def get(self, request):
        form = FinancialRecordForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = FinancialRecordForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial_record_list')
        return render(request, self.template_name, {'form': form})

class FinancialRecordUpdateView(View):
    template_name = 'financial_record/financial_record_form.html'

    def get(self, request, pk):
        financial_record = get_object_or_404(FinancialRecord, pk=pk)
        form = FinancialRecordForm(instance=financial_record)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        financial_record = get_object_or_404(FinancialRecord, pk=pk)
        form = FinancialRecordForm(request.POST, instance=financial_record)
        if form.is_valid():
            form.save()
            return redirect('financial_record_list')
        return render(request, self.template_name, {'form': form})

class FinancialRecordDeleteView(View):
    template_name = 'financial_record/financial_record_confirm_delete.html'

    def get(self, request, pk):
        financial_record = get_object_or_404(FinancialRecord, pk=pk)
        return render(request, self.template_name, {'financial_record': financial_record})

    def post(self, request, pk):
        financial_record = get_object_or_404(FinancialRecord, pk=pk)
        financial_record.delete()
        return redirect('financial_record_list')
