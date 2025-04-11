from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta

# Import ALL your relevant models
from models import (
    Student, Guardian, Class, Session, Term, FeeAssignment,
    StudentFeeRecord, Payment, FinancialRecord
)

CustomUser = get_user_model()

class FinancialModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.admin_user = CustomUser.objects.create_superuser(
            'admin', 'admin@example.com', 'password123', role='admin'
        )
        cls.guardian_user = CustomUser.objects.create_user(
            'guardian1', 'guardian@example.com', 'password123', role='guardian'
        )
        cls.student_user1 = CustomUser.objects.create_user(
            'student1', 'student1@example.com', 'password123', role='student',
            first_name="Alice", last_name="Smith"
        )
        cls.student_user2 = CustomUser.objects.create_user(
            'student2', 'student2@example.com', 'password123', role='student',
            first_name="Bob", last_name="Jones"
        )

        # Create Guardian
        cls.guardian = Guardian.objects.create(user=cls.guardian_user, address="123 Main St")

        # Create Session and Term
        cls.session = Session.objects.create(
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=150),
            is_active=True # Ensure this triggers is_active logic if any
        )
        cls.term = Term.objects.create(
            session=cls.session, name='First Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=60),
            is_active=True # Ensure this triggers is_active logic
        )
        cls.inactive_term = Term.objects.create(
            session=cls.session, name='Previous Term',
            start_date=date.today() - timedelta(days=120),
            end_date=date.today() - timedelta(days=31),
            is_active=False # Explicitly inactive
        )


        # Create Class
        cls.class1 = Class.objects.create(name='JSS 1')

        # Create Students
        cls.student1 = Student.objects.create(
            user=cls.student_user1, date_of_birth=date(2010, 5, 15), gender='F',
            student_guardian=cls.guardian, relationship="Daughter", current_class=cls.class1
        )
        cls.student2 = Student.objects.create(
            user=cls.student_user2, date_of_birth=date(2011, 3, 20), gender='M',
            student_guardian=cls.guardian, relationship="Son", current_class=cls.class1
        )

        # Create Fee Assignment
        cls.fee_assignment = FeeAssignment.objects.create(
            class_instance=cls.class1, term=cls.term, amount=Decimal('50000.00')
        )

    def test_student_fee_record_creation_and_net_fee(self):
        """Test net_fee calculation on StudentFeeRecord creation."""
        record = StudentFeeRecord.objects.create(
            student=self.student1,
            term=self.term,
            fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount,
            discount=Decimal('5000.00'),
            waiver=False
        )
        self.assertEqual(record.net_fee, Decimal('45000.00'))

    def test_student_fee_record_waiver(self):
        """Test net_fee is zero when waiver is True."""
        record = StudentFeeRecord.objects.create(
            student=self.student1,
            term=self.term,
            fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount,
            discount=Decimal('5000.00'),
            waiver=True # Set waiver
        )
        self.assertEqual(record.net_fee, Decimal('0.00'))

        # Test toggling waiver back
        record.waiver = False
        record.save()
        self.assertEqual(record.net_fee, Decimal('45000.00')) # Assumes discount remains

    def test_financial_record_creation_via_signal(self):
        """Test FinancialRecord is created/updated when StudentFeeRecord is saved."""
        self.assertEqual(FinancialRecord.objects.count(), 0)
        sfr = StudentFeeRecord.objects.create(
            student=self.student1,
            term=self.term,
            fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount,
            discount=Decimal('2000.00')
        )
        # Signal should have run
        self.assertEqual(FinancialRecord.objects.count(), 1)
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        self.assertEqual(fr.total_fee, sfr.net_fee) # total_fee is net_fee
        self.assertEqual(fr.total_discount, sfr.discount)
        self.assertEqual(fr.total_paid, Decimal('0.00'))
        self.assertEqual(fr.outstanding_balance, sfr.net_fee)
        # Term is active, so archived should be False (check Term active status logic)
        # self.assertFalse(fr.archived) # Depends on term status and signal logic

    def test_financial_record_update_on_discount_change_via_signal(self):
        """Test FinancialRecord updates when StudentFeeRecord discount changes."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('1000.00')
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        initial_balance = fr.outstanding_balance

        # Change discount and save StudentFeeRecord
        sfr.discount = Decimal('5000.00')
        sfr.save() # Triggers signal

        fr.refresh_from_db() # Reload from DB
        self.assertEqual(fr.total_fee, Decimal('45000.00')) # New net fee
        self.assertEqual(fr.total_discount, Decimal('5000.00'))
        self.assertEqual(fr.total_paid, Decimal('0.00')) # No payment yet
        self.assertEqual(fr.outstanding_balance, Decimal('45000.00'))
        self.assertNotEqual(fr.outstanding_balance, initial_balance)

    def test_financial_record_update_on_waiver_change_via_signal(self):
        """Test FinancialRecord updates when StudentFeeRecord waiver changes."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('1000.00'), waiver=False
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        sfr.waiver = True
        sfr.save() # Triggers signal

        fr.refresh_from_db()
        self.assertEqual(fr.total_fee, Decimal('0.00')) # Net fee is 0
        self.assertEqual(fr.total_discount, Decimal('1000.00')) # Discount still recorded
        self.assertEqual(fr.outstanding_balance, Decimal('0.00'))

        sfr.waiver = False
        sfr.save()

        fr.refresh_from_db()
        self.assertEqual(fr.total_fee, Decimal('49000.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('49000.00'))

    def test_payment_creation_updates_financial_record_via_signal(self):
        """Test FinancialRecord updates when Payment is created."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('0.00')
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        # Create payment
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('20000.00'))

        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('20000.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('30000.00')) # 50000 - 20000

    def test_multiple_payments_update_financial_record(self):
        """Test multiple payments correctly update FinancialRecord."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('0.00')
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        Payment.objects.create(financial_record=fr, amount_paid=Decimal('15000.00'))
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('10000.00'))

        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('25000.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('25000.00'))

    def test_payment_update_updates_financial_record(self):
        """Test FinancialRecord updates correctly when a Payment amount is changed."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('0.00')
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        payment = Payment.objects.create(financial_record=fr, amount_paid=Decimal('10000.00'))

        # Update payment
        payment.amount_paid = Decimal('12000.00')
        payment.save() # Triggers signal

        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('12000.00'))
        self.assertEqual(fr.outstanding_balance, Decimal('38000.00'))

    def test_payment_deletion_updates_financial_record(self):
        """Test FinancialRecord updates correctly when a Payment is deleted."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('0.00')
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        payment1 = Payment.objects.create(financial_record=fr, amount_paid=Decimal('10000.00'))
        payment2 = Payment.objects.create(financial_record=fr, amount_paid=Decimal('5000.00'))

        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('15000.00'))

        # Delete one payment
        payment1.delete() # Triggers signal

        fr.refresh_from_db()
        self.assertEqual(fr.total_paid, Decimal('5000.00')) # Only payment2 remains
        self.assertEqual(fr.outstanding_balance, Decimal('45000.00'))

    def test_payment_validation_overpayment(self):
        """Test ValidationError on attempt to pay more than net_fee."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, discount=Decimal('40000.00') # Net Fee = 10000
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        # First payment okay
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('5000.00'))

        # Second payment exceeds total net fee
        with self.assertRaises(ValidationError):
            payment_over = Payment(financial_record=fr, amount_paid=Decimal('6000.00'))
            payment_over.full_clean() # clean() method should raise the error

    def test_payment_validation_on_waiver(self):
        """Test ValidationError on attempt to pay when waiver is active."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=self.fee_assignment.amount, waiver=True # Waiver active
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)
        self.assertEqual(fr.total_fee, Decimal('0.00'))

        with self.assertRaises(ValidationError):
            payment_waived = Payment(financial_record=fr, amount_paid=Decimal('100.00'))
            payment_waived.full_clean()

    def test_financial_record_can_access_results_property(self):
        """Test the can_access_results logic."""
        sfr = StudentFeeRecord.objects.create(
            student=self.student1, term=self.term, fee_assignment=self.fee_assignment,
            amount=Decimal('100000.00'), discount=Decimal('0.00') # Net Fee = 100k
        )
        fr = FinancialRecord.objects.get(student=self.student1, term=self.term)

        # Scenario 1: No payment
        self.assertFalse(fr.can_access_results)

        # Scenario 2: Partial payment < 80% (e.g., 50k)
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('50000.00'))
        fr.refresh_from_db()
        self.assertFalse(fr.can_access_results)

        # Scenario 3: Partial payment >= 80% (e.g., 80k)
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('30000.00')) # Total = 80k
        fr.refresh_from_db()
        self.assertTrue(fr.can_access_results)

        # Scenario 4: Full payment (e.g., 100k)
        Payment.objects.create(financial_record=fr, amount_paid=Decimal('20000.00')) # Total = 100k
        fr.refresh_from_db()
        self.assertTrue(fr.is_fully_paid)
        self.assertTrue(fr.can_access_results)

        # Scenario 5: Waiver active
        sfr.waiver = True
        sfr.save() # Signal updates FR
        fr.refresh_from_db()
        self.assertTrue(fr.has_waiver)
        self.assertTrue(fr.can_access_results) # Access granted due to waiver