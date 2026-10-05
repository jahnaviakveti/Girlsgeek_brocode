import re

with open('app/api/routes/coach.py', 'r') as f:
    main_content = f.read()

with open('coach_append.py', 'r') as f:
    append_content = f.read()

# Split append_content into imports and endpoints
import_section, endpoints_section = append_content.split('# --- ENDPOINTS TO APPEND ---')

# Inject imports into main_content near the top
if "CareerExecutionService" not in main_content:
    main_content = re.sub(
        r'(from app.db.database import get_db, init_db)',
        import_section.strip() + r'\n\n\1',
        main_content
    )

# Inject singletons
singletons = """
_career_execution_service = CareerExecutionService(
    vault_service=_vault_service,
    job_fit_service=_job_fit_service,
    validation_service=_validation_service,
)
_showcase_service = CareerShowcaseService()
"""
if "_career_execution_service =" not in main_content:
    main_content = re.sub(
        r'(_career_intelligence_service = CareerIntelligenceService\(job_fit_service=_job_fit_service\)\n)',
        r'\1' + singletons + '\n',
        main_content
    )

# Append endpoints
main_content = main_content.strip() + "\n\n" + endpoints_section.strip() + "\n"

with open('app/api/routes/coach.py', 'w') as f:
    f.write(main_content)

print("Merge complete!")
