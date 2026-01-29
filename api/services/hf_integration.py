import os
import logging
from huggingface_hub import HfApi, upload_folder

logger = logging.getLogger(__name__)

class HFManager:
    def __init__(self, repo_id=None, token=None):
        self.repo_id = repo_id or os.getenv("HF_REPO_ID")
        self.token = token or os.getenv("HF_TOKEN")
        
        if not self.repo_id:
            logger.warning("HF_REPO_ID not set. Push disabled.")
        if not self.token:
            logger.warning("HF_TOKEN not set. Read-only mode.")
            
        self.api = HfApi(token=self.token)

    def push_dataset(self, folder_path, path_in_repo="data"):
        """
        Pushes a local folder to the HF Hub dataset.
        """
        if not self.repo_id or not self.token:
            logger.info("Skipping HF Push: Credentials missing.")
            return
            
        try:
            logger.info(f"Pushing {folder_path} to {self.repo_id}...")
            upload_folder(
                folder_path=folder_path,
                path_in_repo=path_in_repo,
                repo_id=self.repo_id,
                repo_type="dataset",
                token=self.token,
                commit_message=f"Auto-update: {os.path.basename(folder_path)}"
            )
            logger.info("HF Push Complete.")
        except Exception as e:
            logger.error(f"HF Push Failed: {e}")
