"""Firm-scoped GraphQL API for bookkeeping client businesses.

Do not attach Relay Node to BookkeepingClient: a generic node(id) lookup must
not expose client records without tenant membership checks.
"""

import graphene
from django.core.exceptions import ValidationError
from graphql_relay import from_global_id
from graphql import GraphQLError

from apps.multitenancy.models import Tenant, TenantMembership

from .models import BookkeepingClient


def _authorized_tenant(info, tenant_id):
    """Require a valid TenantType Relay ID and an *accepted* membership."""
    user = getattr(info.context, "user", None)
    if user is None or not user.is_authenticated:
        raise GraphQLError("Authentication required")

    try:
        kind, pk = from_global_id(tenant_id)
    except (ValueError, TypeError):
        raise GraphQLError("Invalid tenant ID")
    if kind != "TenantType" or not pk:
        raise GraphQLError("Invalid tenant ID")

    membership = (
        TenantMembership.objects.select_related("tenant")
        .filter(user=user, tenant_id=pk, is_accepted=True)
        .first()
    )
    if membership is None:
        raise GraphQLError("Tenant access denied")
    return membership.tenant


class BookkeepingClientType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    contact_email = graphene.String(required=True)
    is_active = graphene.Boolean(required=True)
    created_at = graphene.DateTime(required=True)
    updated_at = graphene.DateTime(required=True)


class Query(graphene.ObjectType):
    bookkeeping_clients = graphene.List(
        graphene.NonNull(BookkeepingClientType),
        tenant_id=graphene.ID(required=True),
        required=True,
    )
    bookkeeping_client = graphene.Field(
        BookkeepingClientType,
        tenant_id=graphene.ID(required=True),
        client_id=graphene.ID(required=True),
    )

    @staticmethod
    def resolve_bookkeeping_clients(root, info, tenant_id):
        tenant = _authorized_tenant(info, tenant_id)
        return BookkeepingClient.objects.filter(tenant=tenant).order_by("name", "id")

    @staticmethod
    def resolve_bookkeeping_client(root, info, tenant_id, client_id):
        tenant = _authorized_tenant(info, tenant_id)
        return BookkeepingClient.objects.filter(tenant=tenant, pk=client_id).first()


class CreateBookkeepingClient(graphene.Mutation):
    class Arguments:
        tenant_id = graphene.ID(required=True)
        name = graphene.String(required=True)
        contact_email = graphene.String()
        
    client = graphene.Field(BookkeepingClientType, required=True)

    @classmethod
    def mutate(cls, root, info, tenant_id, name, contact_email=""):
        tenant = _authorized_tenant(info, tenant_id)
        name = name.strip()
        if not name:
            raise GraphQLError("Client name is required")
        client = BookkeepingClient(tenant=tenant, name=name, contact_email=contact_email.strip())
        try:
            client.full_clean()
        except ValidationError as exc:
            raise GraphQLError(str(exc))
        client.save()
        return cls(client=client)


class UpdateBookkeepingClient(graphene.Mutation):
    class Arguments:
        tenant_id = graphene.ID(required=True)
        client_id = graphene.ID(required=True)
        name = graphene.String()
        contact_email = graphene.String()
        is_active = graphene.Boolean()

    client = graphene.Field(BookkeepingClientType, required=True)

    @classmethod
    def mutate(cls, root, info, tenant_id, client_id, name=None, contact_email=None, is_active=None):
        tenant = _authorized_tenant(info, tenant_id)
        client = BookkeepingClient.objects.filter(tenant=tenant, pk=client_id).first()
        if client is None:
            raise GraphQLError("Client not found")

        if name is not None:
            client.name = name.strip()
            if not client.name:
                raise GraphQLError("Client name is required")
        if contact_email is not None:
            client.contact_email = contact_email.strip()
        if is_active is not None:
            client.is_active = is_active

        try:
            client.full_clean()
        except ValidationError as exc:
            raise GraphQLError(str(exc))
        client.save()
        return cls(client=client)


class Mutation(graphene.ObjectType):
    create_bookkeeping_client = CreateBookkeepingClient.Field()
    update_bookkeeping_client = UpdateBookkeepingClient.Field()
