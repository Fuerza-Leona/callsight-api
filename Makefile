run:
	docker build -t callsight-api .
	docker run -p 8000:8000 -v $(PWD):/app --env-file .env callsight-api