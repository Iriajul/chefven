# apps/users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import WorkerProfile

User = get_user_model()

class WorkerStep1Serializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data.pop('password2'):
            raise serializers.ValidationError("Passwords do not match")
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already exists")
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            user_type='worker'
        )
        return user


class WorkerStep2Serializer(serializers.ModelSerializer):
    skills = serializers.ListField(child=serializers.CharField(max_length=100))

    class Meta:
        model = WorkerProfile
        fields = ['profession', 'hourly_rate', 'skills', 'experience_years']

    def create(self, validated_data):
        worker_profile = WorkerProfile.objects.create(
            user=self.context['user'],
            **validated_data
        )
        # Mark user profile as complete
        self.context['user'].is_profile_complete = True
        self.context['user'].save()
        return worker_profile
    

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'),
                                username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password")
            if not user.is_active:
                raise serializers.ValidationError("Account is disabled")
        else:
            raise serializers.ValidationError("Email and password are required")

        data['user'] = user
        return data    
    
 # ==================== BONUS: Profession List (for dropdown) ====================
class ProfessionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()

    class Meta:
        fields = ['value', 'label']   
    
# ==================== FORGOT PASSWORD FLOW (Token-Based) ====================
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value, is_active=True).exists():
            # Security: Don't reveal if email exists
            return value
        return value


class VerifyOtpSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    otp = serializers.CharField(max_length=4, min_length=4)

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    temp_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return data


class ClientSignupSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if data['password'] != data.pop('password2'):
            raise serializers.ValidationError({"password2": "Passwords do not match"})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "This email is already registered"})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            user_type='client',           # ← CLIENT
            is_profile_complete=True      # ← No Step 2 → complete immediately
        )
        return user