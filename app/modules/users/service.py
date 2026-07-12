from typing import List, Dict, Any, Optional

class UsersService:
    def __init__(self):
        # In-memory database simulation (like a simple repository or array in NestJS service)
        self._users: List[Dict[str, Any]] = []
        self._id_counter = 1

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        new_user = {
            "id": self._id_counter,
            "email": user_data["email"],
            "username": user_data["username"],
            "is_active": True
        }
        self._users.append(new_user)
        self._id_counter += 1
        return new_user

    def get_all_users(self) -> List[Dict[str, Any]]:
        return self._users

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        for user in self._users:
            if user["id"] == user_id:
                return user
        return None

# Singleton instance of the service (default provider behavior in NestJS)
users_service = UsersService()
