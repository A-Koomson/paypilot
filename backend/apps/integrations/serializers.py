from __future__ import annotations

from rest_framework import serializers

from apps.integrations.models import PayPalInvoice, PayPalTransaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalTransaction
        fields = [
            "id",
            "source_id",
            "status",
            "event_code",
            "amount",
            "currency",
            "initiated_at",
            "updated_at_source",
            "payer_email",
            "note",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalInvoice
        fields = [
            "id",
            "source_id",
            "invoice_number",
            "status",
            "amount",
            "due_amount",
            "currency",
            "invoice_date",
            "due_date",
            "recipient_email",
        ]
