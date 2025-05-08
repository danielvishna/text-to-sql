USE master;
GO

IF EXISTS (SELECT * FROM sys.databases WHERE name = 'AdventureWorks2022')
BEGIN
    ALTER DATABASE AdventureWorks2022 SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE AdventureWorks2022;
END
GO

RESTORE DATABASE AdventureWorks2022
FROM DISK = N'/opt/mssql/backup/AdventureWorks2022.bak'
WITH MOVE 'AdventureWorks2022' TO '/var/opt/mssql/data/AdventureWorks2022.mdf',
     MOVE 'AdventureWorks2022_log' TO '/var/opt/mssql/data/AdventureWorks2022_log.ldf',
     REPLACE;
GO
