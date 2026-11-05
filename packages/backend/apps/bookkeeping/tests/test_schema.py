import pytest
from graphql_relay import to_global_id

from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.bookkeeping.models import BookkeepingClient

pytestmark = pytest.mark.django_db


LIST_QUERY = """
query ($tenantId: ID!) {
  bookkeepingClients(tenantId: $tenantId) { id name contactEmail isActive }
}
"""
DETAIL_QUERY = """
query ($tenantId: ID!, $clientId: ID!) {
  bookkeepingClient(tenantId: $tenantId, clientId: $clientId) { id name }
}
"""
CREATE_MUTATION = """
mutation ($tenantId: ID!, $name: String!, $contactEmail: String) {
  createBookkeepingClient(tenantId: $tenantId, name: $name, contactEmail: $contactEmail) {
    client { id name contactEmail }
  }
}
"""
UPDATE_MUTATION = """
mutation ($tenantId: ID!, $clientId: ID!, $name: String) {
  updateBookkeepingClient(tenantId: $tenantId, clientId: $clientId, name: $name) {
    client { id name }
  }
}
"""


def tenant_global_id(tenant):
    return to_global_id("TenantType", tenant.id)


def test_member_lists_only_current_firm_clients(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    firm_a = tenant_factory(type=TenantType.ORGANIZATION)
    firm_b = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=firm_a, user=user, role=TenantUserRole.OWNER, is_accepted=True)
    own = BookkeepingClient.objects.create(tenant=firm_a, name="Own Client")
    BookkeepingClient.objects.create(tenant=firm_b, name="Other Client")
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(firm_a, TenantUserRole.OWNER)
    result = graphene_client.query(LIST_QUERY, variable_values={"tenantId": tenant_global_id(firm_a)})
    assert "errors" not in result, result.get("errors")
    assert [(x["id"], x["name"]) for x in result["data"]["bookkeepingClients"]] == [
        (str(own.pk), own.name)
    ]


def test_nonmember_cannot_list_or_create(
    graphene_client, user, tenant_factory
):
    firm = tenant_factory(type=TenantType.ORGANIZATION)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(firm, None)
    variables = {"tenantId": tenant_global_id(firm)}
    result = graphene_client.query(LIST_QUERY, variable_values=variables)
    assert result.get("errors")
    result = graphene_client.mutate(CREATE_MUTATION, variable_values={**variables, "name": "Blocked"})
    assert result.get("errors")
    assert not BookkeepingClient.objects.filter(name="Blocked").exists()


def test_unaccepted_invitation_does_not_grant_access(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    firm = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=firm, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(firm, None)
    result = graphene_client.query(LIST_QUERY, variable_values={"tenantId": tenant_global_id(firm)})
    assert result.get("errors")


def test_create_and_update_are_tenant_scoped(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    firm_a = tenant_factory(type=TenantType.ORGANIZATION)
    firm_b = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=firm_a, user=user, role=TenantUserRole.OWNER, is_accepted=True)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(firm_a, TenantUserRole.OWNER)
    created = graphene_client.mutate(
        CREATE_MUTATION,
        variable_values={"tenantId": tenant_global_id(firm_a), "name": "Studio", "contactEmail": "hi@example.com"},
    )
    assert not created.get("errors"), created.get("errors")
    client_id = created["data"]["createBookkeepingClient"]["client"]["id"]
    assert BookkeepingClient.objects.get(pk=client_id).tenant_id == firm_a.id
    changed = graphene_client.mutate(
        UPDATE_MUTATION,
        variable_values={"tenantId": tenant_global_id(firm_a), "clientId": client_id, "name": "Studio Two"},
    )
    assert not changed.get("errors"), changed.get("errors")
    assert BookkeepingClient.objects.get(pk=client_id).name == "Studio Two"
    BookkeepingClient.objects.create(tenant=firm_b, name="Hidden")
    refused = graphene_client.mutate(
        UPDATE_MUTATION,
        variable_values={"tenantId": tenant_global_id(firm_b), "clientId": client_id, "name": "Stolen"},
    )
    assert refused.get("errors")
    assert BookkeepingClient.objects.get(pk=client_id).name == "Studio Two"


def test_detail_cannot_read_other_firm_client(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    firm_a = tenant_factory(type=TenantType.ORGANIZATION)
    firm_b = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=firm_a, user=user, role=TenantUserRole.OWNER, is_accepted=True)
    other = BookkeepingClient.objects.create(tenant=firm_b, name="Private")
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(firm_a, TenantUserRole.OWNER)
    result = graphene_client.query(
        DETAIL_QUERY, variable_values={"tenantId": tenant_global_id(firm_a), "clientId": str(other.pk)}
    )
    assert not result.get("errors"), result.get("errors")
    assert result["data"]["bookkeepingClient"] is None


def test_anonymous_cannot_view_clients(graphene_client, tenant_factory):
    firm = tenant_factory(type=TenantType.ORGANIZATION)
    result = graphene_client.query(LIST_QUERY, variable_values={"tenantId": tenant_global_id(firm)})
    assert result.get("errors")
