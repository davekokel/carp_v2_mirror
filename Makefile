er:
	SCHEMAS="public" DB_PASS="diagram_only_pw" bash scripts/er_schema.sh schema_report
er-all:
	SCHEMAS="public,raw" DB_PASS="diagram_only_pw" bash scripts/er_schema.sh schema_report_public_raw
