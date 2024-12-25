from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, Guardian, Teacher
from datetime import date

CustomUser = get_user_model()

class LoginTests(TestCase):

    def setUp(self):
        # Set up test users
        self.student_user = CustomUser.objects.create_user(
            username="test_student",
            password="testpassword123",
            role="student"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            date_of_birth="2010-01-01",
            gender="M",
            relationship="Father",
        )

        self.guardian_user = CustomUser.objects.create_user(
            username="test_guardian",
            password="testpassword123",
            role="guardian"
        )
        self.guardian = Guardian.objects.create(
            user=self.guardian_user,
            gender="M",
            contact="1234567890",
            address="123 Main Street"
        )

        self.teacher_user = CustomUser.objects.create_user(
            username="test_teacher",
            password="testpassword123",
            role="teacher"
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            date_of_birth="1985-01-01",
            gender="F",
            contact="9876543210",
            address="456 Elm Street"
        )

    def test_student_login(self):
        # Attempt to log in as the student
        login = self.client.login(username="test_student", password="testpassword123")
        self.assertTrue(login, "Student login failed")
        
        # Verify user role
        user = CustomUser.objects.get(username="test_student")
        self.assertEqual(user.role, "student", "User role mismatch for student login")
        self.assertTrue(hasattr(user, "student"), "Student instance missing for user")

    def test_guardian_login(self):
        # Attempt to log in as the guardian
        login = self.client.login(username="test_guardian", password="testpassword123")
        self.assertTrue(login, "Guardian login failed")
        
        # Verify user role
        user = CustomUser.objects.get(username="test_guardian")
        self.assertEqual(user.role, "guardian", "User role mismatch for guardian login")
        self.assertTrue(hasattr(user, "guardian"), "Guardian instance missing for user")

    def test_teacher_login(self):
        # Attempt to log in as the teacher
        login = self.client.login(username="test_teacher", password="testpassword123")
        self.assertTrue(login, "Teacher login failed")
        
        # Verify user role
        user = CustomUser.objects.get(username="test_teacher")
        self.assertEqual(user.role, "teacher", "User role mismatch for teacher login")
        self.assertTrue(hasattr(user, "teacher"), "Teacher instance missing for user")

    def test_invalid_login(self):
        # Attempt to log in with invalid credentials
        login = self.client.login(username="invalid_user", password="invalidpassword")
        self.assertFalse(login, "Invalid login should fail")

    def test_user_roles(self):
        # Ensure roles are correctly assigned
        self.assertEqual(self.student_user.role, "student", "Student role incorrect")
        self.assertEqual(self.guardian_user.role, "guardian", "Guardian role incorrect")
        self.assertEqual(self.teacher_user.role, "teacher", "Teacher role incorrect")
