login:
	gcloud auth login
	gcloud auth application-default login
	
deploy-stream-downloader:
	gcloud run jobs deploy stream-downloader \
		--source . \
		--project ravineo-tv \
		--region europe-west1 \
		--memory 1Gi \
		--max-retries 0 \
		--task-timeout 1h \
		--set-secrets "MONGODB_URI=MONGODB_URI:latest" \
		--set-env-vars "STORAGE_BASE_DIR=/storage" \
		--command poetry,run,python,school_project/stream_downloader.py
