from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any

# SCIM Schemas: https://tools.ietf.org/html/rfc7643
# We'll implement a subset for user and group provisioning.

class SCIMMeta(BaseModel):
    resource_type: str = Field(..., alias="resourceType")
    location: Optional[str] = None
    version: Optional[str] = None
    created: Optional[str] = None
    last_modified: Optional[str] = Field(None, alias="lastModified")

class SCIMName(BaseModel):
    given_name: Optional[str] = Field(None, alias="givenName")
    family_name: Optional[str] = Field(None, alias="familyName")
    formatted: Optional[str] = None

class SCIMEmail(BaseModel):
    value: EmailStr
    primary: bool = True
    type: str = "work"

class SCIMUser(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:User"]
    id: Optional[str] = None
    external_id: Optional[str] = Field(None, alias="externalId")
    user_name: str = Field(..., alias="userName")
    name: Optional[SCIMName] = None
    display_name: Optional[str] = Field(None, alias="displayName")
    emails: Optional[List[SCIMEmail]] = None
    active: bool = True
    meta: Optional[SCIMMeta] = None

    class Config:
        populate_by_name = True

class SCIMListResponse(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    total_results: int = Field(..., alias="totalResults")
    start_index: int = Field(..., alias="startIndex")
    items_per_page: int = Field(..., alias="itemsPerPage")
    resources: List[Dict[str, Any]] = Field([], alias="Resources")

class SCIMMember(BaseModel):
    value: str # The 'id' of the user
    display: Optional[str] = None # The 'userName' of the user

class SCIMGroup(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:schemas:core:2.0:Group"]
    id: Optional[str] = None
    external_id: Optional[str] = Field(None, alias="externalId")
    display_name: str = Field(..., alias="displayName")
    members: Optional[List[SCIMMember]] = []
    meta: Optional[SCIMMeta] = None

    class Config:
        populate_by_name = True
        
class SCIMPatchOp(BaseModel):
    op: str # "add", "remove", "replace"
    path: Optional[str] = None
    value: Optional[Any] = None

class SCIMPatchRequest(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    operations: List[SCIMPatchOp] = Field(..., alias="Operations")
