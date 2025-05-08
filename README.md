## How To Run?

To run this project you first have to add your own openai api key to the backend's environment in docker-compose.yml, like this:

    environment:
      - DB_SERVER=host.docker.internal
      - DB_USER=sa
      - DB_PASSWORD=StrongPassword123!
      - DB_NAME=AdventureWorks2022
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - OPENAI_API_KEY=[your key]

Than, run the project by opening starting docker and running:

```
docker compose up -d
```

After about 60-90 seconds, go to your browser and visit the url http://localhost/ where you can see my awesome project:

![alt text](image.png)
