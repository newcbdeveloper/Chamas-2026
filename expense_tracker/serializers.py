from rest_framework import serializers
from .models import Transaction, Category, Budget, RecurringTransaction, Insight


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'icon', 'color', 'is_default']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    signed_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'category', 'category_name', 'category_icon', 
            'category_color', 'amount', 'signed_amount', 'description', 
            'date', 'time', 'is_recurring', 'created_at'
        ]
        read_only_fields = ['created_at', 'signed_amount']


class BudgetSerializer(serializers.ModelSerializer):
    """Serializer for Budget model"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    spent_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    percentage_used = serializers.SerializerMethodField()
    
    class Meta:
        model = Budget
        fields = [
            'id', 'category', 'category_name', 'category_icon', 'amount', 
            'period', 'spent_amount', 'remaining_amount', 'percentage_used',
            'rollover_enabled', 'alert_threshold', 'is_active'
        ]
    
    def get_spent_amount(self, obj):
        return float(obj.get_spent_amount())
    
    def get_remaining_amount(self, obj):
        return float(obj.get_remaining_amount())
    
    def get_percentage_used(self, obj):
        return float(obj.get_percentage_used())


class RecurringTransactionSerializer(serializers.ModelSerializer):
    """Serializer for RecurringTransaction model"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = RecurringTransaction
        fields = [
            'id', 'type', 'category', 'category_name', 'amount', 
            'description', 'frequency', 'start_date', 'end_date',
            'next_occurrence', 'is_active', 'auto_generate'
        ]


class InsightSerializer(serializers.ModelSerializer):
    """Serializer for Insight model"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Insight
        fields = [
            'id', 'type', 'title', 'message', 'category', 
            'category_name', 'is_read', 'created_at'
        ]
        read_only_fields = ['created_at']