"""Home Assistant todo list synchronization."""

from datetime import datetime
from typing import Callable, Any

from src.tasks.models import Task, TaskStatus
from src.tasks.store import TaskStore


class HomeAssistantSync:
    """Bidirectional sync with Home Assistant todo lists."""

    # Known HA lists
    HA_LISTS = ["Dag til dag", "Handleliste"]

    def __init__(
        self,
        store: TaskStore,
        get_items_func: Callable[..., Any],
        add_item_func: Callable[..., Any],
        complete_item_func: Callable[..., Any],
    ):
        """Initialize HA sync.

        Args:
            store: TaskStore instance
            get_items_func: Function to get items from HA (mcp__homeassistant__assist__todo_get_items)
            add_item_func: Function to add item to HA (mcp__homeassistant__assist__HassListAddItem)
            complete_item_func: Function to complete item in HA (mcp__homeassistant__assist__HassListCompleteItem)
        """
        self._store = store
        self._get_items = get_items_func
        self._add_item = add_item_func
        self._complete_item = complete_item_func

    def pull_from_ha(self, list_name: str) -> list[Task]:
        """Pull tasks from HA that don't exist locally.

        Returns list of newly created local tasks.
        """
        # Get items from HA
        try:
            ha_items = self._get_items(todo_list=list_name, status="needs_action")
        except Exception:
            return []

        if not ha_items:
            return []

        # Get existing local tasks for this list
        local_tasks = self._store.get_tasks_by_ha_list(list_name)
        local_titles = {t.title.lower() for t in local_tasks}

        # Create local tasks for new HA items
        new_tasks = []
        for item in ha_items:
            title = item.get("summary") or item.get("item") or str(item)
            if title.lower() not in local_titles:
                task = self._store.create_task(
                    title=title,
                    ha_list_name=list_name,
                )
                new_tasks.append(task)

        return new_tasks

    def push_to_ha(self, task: Task) -> bool:
        """Push a local task to HA list.

        Returns True if successful.
        """
        if not task.ha_list_name:
            return False

        try:
            self._add_item(name=task.ha_list_name, item=task.title)
            self._store.update_ha_sync_status(task.id, ha_item_id=task.title)
            return True
        except Exception:
            return False

    def sync_completion(self, task: Task) -> bool:
        """Sync task completion status with HA.

        Returns True if successful.
        """
        if not task.ha_list_name or task.status != TaskStatus.COMPLETED:
            return False

        try:
            self._complete_item(name=task.ha_list_name, item=task.title)
            return True
        except Exception:
            return False

    def full_sync(self, list_name: str) -> dict:
        """Full bidirectional sync with an HA list.

        Returns dict with sync statistics.
        """
        stats = {
            "pulled": 0,
            "pushed": 0,
            "completed": 0,
            "errors": 0,
        }

        # Pull new items from HA
        try:
            new_tasks = self.pull_from_ha(list_name)
            stats["pulled"] = len(new_tasks)
        except Exception:
            stats["errors"] += 1

        # Push local tasks that haven't been synced
        local_tasks = self._store.get_tasks_by_ha_list(list_name)
        for task in local_tasks:
            if task.ha_synced_at is None and task.status == TaskStatus.PENDING:
                if self.push_to_ha(task):
                    stats["pushed"] += 1
                else:
                    stats["errors"] += 1

        # Sync completions
        for task in local_tasks:
            if task.status == TaskStatus.COMPLETED and task.ha_synced_at:
                if self.sync_completion(task):
                    stats["completed"] += 1

        return stats

    def sync_all_lists(self) -> dict:
        """Sync all known HA lists.

        Returns combined stats.
        """
        total_stats = {
            "pulled": 0,
            "pushed": 0,
            "completed": 0,
            "errors": 0,
        }

        for list_name in self.HA_LISTS:
            stats = self.full_sync(list_name)
            for key in total_stats:
                total_stats[key] += stats[key]

        return total_stats
