# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .forms import AttendanceForm, ClassForm
from ..models import Attendance

# Attendance Views
class AttendanceListView(View):
    template_name = 'attendance/attendance_list.html'

    def get(self, request, *args, **kwargs):
        attendance_list = Attendance.objects.all()
        return render(request, self.template_name, {'attendance_list': attendance_list})

class AttendanceCreateView(View):
    template_name = 'attendance/attendance_form.html'

    def get(self, request, *args, **kwargs):
        form = AttendanceForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = AttendanceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('attendance_list')
        return render(request, self.template_name, {'form': form})

class AttendanceUpdateView(View):
    template_name = 'attendance/attendance_form.html'

    def get(self, request, pk, *args, **kwargs):
        attendance = get_object_or_404(Attendance, pk=pk)
        form = AttendanceForm(instance=attendance)
        return render(request, self.template_name, {'form': form, 'is_update': True})

    def post(self, request, pk, *args, **kwargs):
        attendance = get_object_or_404(Attendance, pk=pk)
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            return redirect('attendance_list')
        return render(request, self.template_name, {'form': form, 'is_update': True})

class AttendanceDeleteView(View):
    template_name = 'attendance/attendance_confirm_delete.html'

    def get(self, request, pk, *args, **kwargs):
        attendance = get_object_or_404(Attendance, pk=pk)
        return render(request, self.template_name, {'attendance': attendance})

    def post(self, request, pk, *args, **kwargs):
        attendance = get_object_or_404(Attendance, pk=pk)
        attendance.delete()
        return redirect('attendance_list')

class AttendanceDetailView(View):
    template_name = 'attendance/attendance_detail.html'

    def get(self, request, pk, *args, **kwargs):
        attendance = get_object_or_404(Attendance, pk=pk)
        return render(request, self.template_name, {'attendance': attendance})


