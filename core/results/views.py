from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import ResultForm
from ..models import Result

class ResultListView(View):
    template_name = 'result/result_list.html'

    def get(self, request):
        results = Result.objects.all()
        return render(request, self.template_name, {'results': results})

class ResultDetailView(View):
    template_name = 'result/result_detail.html'

    def get(self, request, pk):
        result = get_object_or_404(Result, pk=pk)
        return render(request, self.template_name, {'result': result})

class ResultCreateView(View):
    template_name = 'result/result_form.html'

    def get(self, request):
        form = ResultForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ResultForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('result_list')
        return render(request, self.template_name, {'form': form})

class ResultUpdateView(View):
    template_name = 'result/result_form.html'

    def get(self, request, pk):
        result = get_object_or_404(Result, pk=pk)
        form = ResultForm(instance=result)
        return render(request, self.template_name, {'form': form})

    def post(self, request, pk):
        result = get_object_or_404(Result, pk=pk)
        form = ResultForm(request.POST, instance=result)
        if form.is_valid():
            form.save()
            return redirect('result_list')
        return render(request, self.template_name, {'form': form})

class ResultDeleteView(View):
    template_name = 'result/result_confirm_delete.html'

    def get(self, request, pk):
        result = get_object_or_404(Result, pk=pk)
        return render(request, self.template_name, {'result': result})

    def post(self, request, pk):
        result = get_object_or_404(Result, pk=pk)
        result.delete()
        return redirect('result_list')
