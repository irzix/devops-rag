import asyncio
import asyncssh
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.security import encrypt_data, decrypt_data
from app.modules.servers.models import Server
from app.modules.servers.schema import ServerCreate, ServerUpdate

class ServersService:
    async def create_server(self, session: AsyncSession, server_in: ServerCreate, owner_id: int) -> Server:
        """Create a server registry after encrypting credentials."""
        # Ensure server name is unique
        statement = select(Server).where(Server.name == server_in.name)
        result = await session.exec(statement)
        if result.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server name already registered"
            )

        # Encrypt password or private key before saving to DB
        encrypted_cred = encrypt_data(server_in.credential)

        # Instantiate Server DB record
        new_server = Server(
            name=server_in.name,
            ip_address=server_in.ip_address,
            ssh_port=server_in.ssh_port,
            ssh_username=server_in.ssh_username,
            ssh_auth_type=server_in.ssh_auth_type,
            encrypted_credential=encrypted_cred,
            tags=server_in.tags,
            owner_id=owner_id
        )

        session.add(new_server)
        await session.commit()
        await session.refresh(new_server)
        return new_server

    async def get_all_servers(self, session: AsyncSession, owner_id: int) -> List[Server]:
        """Fetch all servers owned by the user."""
        statement = select(Server).where(Server.owner_id == owner_id)
        result = await session.exec(statement)
        return result.all()

    async def get_server_by_id(self, session: AsyncSession, server_id: int, owner_id: int) -> Optional[Server]:
        """Fetch a specific server by ID and verify ownership."""
        statement = select(Server).where(Server.id == server_id, Server.owner_id == owner_id)
        result = await session.exec(statement)
        server = result.first()
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        return server

    async def get_server_by_name(self, session: AsyncSession, name: str, owner_id: int) -> Optional[Server]:
        """Fetch a specific server by name and verify ownership."""
        statement = select(Server).where(Server.name == name, Server.owner_id == owner_id)
        result = await session.exec(statement)
        server = result.first()
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        return server

    async def update_server(self, session: AsyncSession, server_id: int, server_in: ServerUpdate, owner_id: int) -> Server:
        """Update an existing server registry configuration."""
        server = await self.get_server_by_id(session, server_id, owner_id)
        
        if server_in.name is not None and server_in.name != server.name:
            # Ensure name is unique if changed
            statement = select(Server).where(Server.name == server_in.name)
            result = await session.exec(statement)
            if result.first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Server name already registered"
                )
            server.name = server_in.name

        if server_in.ip_address is not None:
            server.ip_address = server_in.ip_address
        if server_in.ssh_port is not None:
            server.ssh_port = server_in.ssh_port
        if server_in.ssh_username is not None:
            server.ssh_username = server_in.ssh_username
        if server_in.ssh_auth_type is not None:
            server.ssh_auth_type = server_in.ssh_auth_type
        if server_in.credential is not None:
            server.encrypted_credential = encrypt_data(server_in.credential)
        if server_in.tags is not None:
            server.tags = server_in.tags

        session.add(server)
        await session.commit()
        await session.refresh(server)
        return server

    async def delete_server(self, session: AsyncSession, server_id: int, owner_id: int) -> dict:
        """Delete an existing server registry."""
        server = await self.get_server_by_id(session, server_id, owner_id)
        await session.delete(server)
        await session.commit()
        return {"status": "success", "message": f"Server {server_id} deleted successfully"}

    async def execute_ssh_command(self, server: Server, command: str) -> dict:
        """
        Decrypt server connection credentials, establish SSH tunnel,
        execute bash command, and return outputs.
        """
        # Decrypt password or SSH Private Key
        credential = decrypt_data(server.encrypted_credential)

        # Build connection arguments
        conn_args = {
            "host": server.ip_address,
            "port": server.ssh_port,
            "username": server.ssh_username,
            "known_hosts": None, # Bypass host key verification for dynamic servers (warning: MITM vulnerable)
        }

        if server.ssh_auth_type == "password":
            conn_args["password"] = credential
        else:
            try:
                # Import private key object from decrypted PEM string
                key = asyncssh.import_private_key(credential)
                conn_args["client_keys"] = [key]
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid SSH private key format: {str(e)}"
                )

        try:
            # Connect and execute command using asyncssh with 30s timeout
            async def run_command_with_ssh():
                async with asyncssh.connect(**conn_args) as conn:
                    result = await conn.run(command, check=False)
                    return {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_status
                    }
            
            return await asyncio.wait_for(run_command_with_ssh(), timeout=30.0)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"SSH execution timed out after 30 seconds on {server.ip_address}"
            )
        except (asyncssh.Error, OSError) as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"SSH Connection Failed to {server.ip_address}:{server.ssh_port} - {str(e)}"
            )

# Single instance representing the service provider
servers_service = ServersService()
