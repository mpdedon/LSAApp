from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import PaymentForm
from ..models import Payment

class PaymentListView(View):
    template_name = 'payment/payment_list.html'

    def get(self, request):
        payments = Payment.objects.all()
        return render(request, self.template_name, {'payments': payments})

class PaymentDetailView(View):
    template_name = 'payment/payment_detail.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        return render(request, self.template_name, {'payment': payment})

class PaymentCreateView(View):
    template_name = 'payment/payment_form.html'

    def get(self, request):
        form = PaymentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PaymentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('payment_list')
        return render(request, self.template_name, {'form': form})

class PaymentUpdateView(View):
    template_name = 'payment/payment_form.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = PaymentForm(instance=payment)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect('payment_list')
        return render(request, self.template_name, {'form': form})

class PaymentDeleteView(View):
    template_name = 'payment/payment_confirm_delete.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        return render(request, self.template_name, {'payment': payment})

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        payment.delete()
        return redirect('payment_list')
