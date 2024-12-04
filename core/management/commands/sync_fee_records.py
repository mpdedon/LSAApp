from django.core.management.base import BaseCommand
from decimal import Decimal
from core.models import Student, FeeAssignment, StudentFeeRecord

class Command(BaseCommand):
    help = "Synchronize Student Fee Records for all students."

    def handle(self, *args, **kwargs):
        students = Student.objects.filter(current_class__isnull=False)
        for student in students:
            fee_assignments = FeeAssignment.objects.filter(class_instance=student.current_class)
            for assignment in fee_assignments:
                StudentFeeRecord.objects.get_or_create(
                    student=student,
                    term=assignment.term,
                    defaults={
                        'fee_assignment': assignment,
                        'amount': assignment.amount,
                        'discount': Decimal('0.00'),
                        'waiver': False,
                        'net_fee': assignment.calculate_net_fee(assignment.amount, Decimal('0.00'), False),
                    }
                )
        self.stdout.write(self.style.SUCCESS("Fee records synchronized successfully."))
