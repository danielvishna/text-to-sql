FROM mcr.microsoft.com/mssql/server:latest

# Install dependencies and mssql-tools
USER root

# Install curl and mssql-tools
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl -sSL https://packages.microsoft.com/config/debian/9/prod.list -o /etc/apt/sources.list.d/mssql-prod.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 mssql-tools

# Create backup directory and download AdventureWorks2022.bak
RUN mkdir -p /opt/mssql/backup && \
    curl -L -o /opt/mssql/backup/AdventureWorks2022.bak https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks2022.bak
# Revert back to non-root user
USER mssql