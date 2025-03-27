login:
	gcloud auth login
	# gcloud auth application-default login
	
deploy-stream-downloader:
	gcloud run jobs deploy stream-downloader \
		--source . \
		--project ravineo-tv \
		--region europe-west1 \
		--memory 1Gi \
		--max-retries 0 \
		--task-timeout 1h \
		--set-env-vars "MONGODB_URI=mongodb+srv://blahakrystof:6HQsC1OnjF0GIq5O@cluster0.zi1hzha.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" \
		--command poetry,run,python,school_project/stream_downloader.py
