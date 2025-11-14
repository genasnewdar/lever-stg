import logging
from fastapi import APIRouter, HTTPException, status, Request
from app.singleton import prisma
from datetime import datetime, timezone
import os

router = APIRouter(prefix="/api/system/user")

# Set up logging (configure handlers/levels as needed)
logger = logging.getLogger("test")
logger.setLevel(logging.INFO)



# ----------------------------
# System End Student Test
# ----------------------------
@router.post("/login-hook")
async def login_hook(request: Request):
    try:
        print("====================== AUTH0 WEBHOOK ======================")
        
        api_key = request.headers.get("x-api-key")
        if api_key != os.getenv("API_KEY"):
            print("INVALID_API_KEY")
            raise Exception("INVALID_API_KEY")
        
        body: dict = await request.json()
        print(body)
        
        user_id = body.get("user_id")
        if not user_id:
            print("NO_USER_ID")
            raise Exception("NO_USER_ID")
        
        user = await prisma.user.find_first(
            where={
                "auth0_id": user_id
            }
        )
        
        if not user:
            given_name = body.get("given_name")
            last_name = body.get("last_name")
            
            user = await prisma.user.create(
                data={
                    "auth0_id": user_id,
                    "email": body.get("email"),
                    "full_name": f"{given_name} {last_name}",
                    "picture": body.get("picture")
                }
            )
        else:
            if user.is_deleted:
                raise Exception("INVALID_USER")
            
            user = await prisma.user.update(
                where={
                    "auth0_id": user_id
                },
                data={
                    "login_count": {
                        "increment": 1
                    }
                }
            )
        
        # Attempt to auto-provision an Employee record for allowed emails/domains
        try:
            email = body.get("email")
            given_name = body.get("given_name") or ""
            last_name = body.get("last_name") or ""
            full_name = f"{given_name} {last_name}".strip() or (user.full_name if user else None)

            domain_allow = os.getenv("EMPLOYEE_EMAIL_DOMAIN")  # e.g. example.com
            allowlist_raw = os.getenv("EMPLOYEE_ALLOWED_EMAILS", "")  # comma-separated
            allowlist = set([e.strip().lower() for e in allowlist_raw.split(",") if e.strip()])

            is_allowed_employee = False
            if email:
                email_l = email.lower()
                if domain_allow and email_l.endswith(f"@{domain_allow.lower()}"):
                    is_allowed_employee = True
                if email_l in allowlist:
                    is_allowed_employee = True

            if is_allowed_employee and email:
                existing_emp = await prisma.employee.find_first(
                    where={
                        "OR": [
                            {"auth0_id": user_id},
                            {"email": email}
                        ]
                    }
                )

                if existing_emp:
                    if existing_emp.is_deleted:
                        raise Exception("INVALID_EMPLOYEE")
                    if existing_emp.auth0_id != user_id:
                        await prisma.employee.update(
                            where={"id": existing_emp.id},
                            data={"auth0_id": user_id}
                        )
                else:
                    await prisma.employee.create(
                        data={
                            "auth0_id": user_id,
                            "email": email,
                            "full_name": full_name or email,
                        }
                    )
        except Exception as emp_err:
            logger = logging.getLogger("system_user_login_hook")
            logger.error(f"Employee provisioning error: {emp_err}")
        return {
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
