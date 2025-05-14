from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.db.session import get_supabase
from app.api.routes.auth import check_admin_role

router = APIRouter(prefix="/companies", tags=["companies"])

class Company(BaseModel):
    name: str
    logo: str
    category: str


@router.get("/", dependencies=[Depends(check_admin_role)])
async def get_all_companies(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("company_client").select("*").execute()
        return {"companies": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Returns the company name and number of users of each company
@router.get("/companySize")
async def get_company_size(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("company_client").select("*, users(count)").execute()
        dict_response = []
        for company in response.data:
            dict_response.append(
                {
                    "name": company["name"],
                    "size": company["users"][0]["count"] if company["users"] else 0,
                }
            )
        return {"info": dict_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#Returns the users of a given company
@router.get("/{name}/list")
async def get_users_in_company(name: str, supabase: Client = Depends(get_supabase)):
    try:
        company_response = (
            supabase.table("company_client")
            .select("company_id")
            .eq("name", name)
            .execute()
        )

        if not company_response.data:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = company_response.data[0]["company_id"]

        users_response = (
            supabase.table("users").select("*").eq("company_id", company_id).execute()
        )

        return {"participants": users_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/create")
async def create_company(company: Company, supabase: Client = Depends(get_supabase)):
    try:
        responseCategory = supabase.table("category").select("category_id, name").eq("name", company.category).execute()
        print(responseCategory.data[0])
        print(responseCategory.data[0]["category_id"])

        if len(responseCategory.data) == 0:
            raise HTTPException(status_code=404, detail="Category not found")
        
        print(company.name)
        
        company_data = {
            "name": company.name,
            "logo": company.logo,
            "category_id": responseCategory.data[0]["category_id"],
        }

        print(company_data)

        response = supabase.table("company_client").insert(company_data).execute()
        return {"message": "Company created successfully", "company": response.data}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
