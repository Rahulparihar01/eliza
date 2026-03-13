"""
HubSpot CRM Search schema and allow-lists.

Defines the Pydantic models that validate and clamp HubSpot Search API
requests so the LLM-generated payloads never exceed safe limits.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

ObjectType = Literal["contacts", "companies", "deals"]

HUBSPOT_PROPERTIES: dict[str, list[str]] = {
    "contacts": [
        "email", "firstname", "lastname", "company",
        "phone", "createdate", "lastmodifieddate",
    ],
    "companies": [
        "name", "domain", "industry", "phone",
        "createdate", "lastmodifieddate",
    ],
    "deals": [
        "dealname", "amount", "dealstage", "pipeline",
        "closedate", "createdate", "lastmodifieddate",
    ],
}


class HubSpotFilter(BaseModel):
    propertyName: str
    operator: str
    value: Optional[str] = None
    values: Optional[List[str]] = None
    highValue: Optional[str] = None


class HubSpotFilterGroup(BaseModel):
    filters: List[HubSpotFilter] = Field(default_factory=list)


class HubSpotSearchRequest(BaseModel):
    """
    Validated representation of a HubSpot CRM Search API payload.

    The ``clamp`` method enforces server-side caps so an LLM cannot
    generate payloads that exceed the platform-configured limits.
    """

    object_type: ObjectType
    query: Optional[str] = None
    filterGroups: List[HubSpotFilterGroup] = Field(default_factory=list)
    sorts: List[str] = Field(default_factory=list)
    properties: List[str] = Field(default_factory=list)
    limit: int = 50
    after: Optional[str] = None

    def clamp(
        self,
        max_groups: int,
        max_filters_total: int,
        max_filters_per_group: int,
    ) -> "HubSpotSearchRequest":
        """Enforce caps on filter groups, total filters, and allowed properties."""
        self.filterGroups = self.filterGroups[:max_groups]
        total = 0
        for group in self.filterGroups:
            if total >= max_filters_total:
                group.filters = []
                continue
            group.filters = group.filters[:max_filters_per_group]
            total += len(group.filters)

        allowed = HUBSPOT_PROPERTIES.get(self.object_type, [])
        self.properties = [p for p in self.properties if p in allowed]
        self.sorts = [s for s in self.sorts if s in allowed]
        self.limit = min(max(self.limit, 1), 50)
        return self
