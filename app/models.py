from pydantic import BaseModel, Field
from typing import Literal

BuildProfile = Literal["python_compile","python_tests","node_tests","dotnet_build","cmake_build","unreal_build","list_files","git_status","git_diff"]

class PromptRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=12000)
    project_name: str = Field(default="NewProject", min_length=1, max_length=80)

class BuildRequest(BaseModel):
    profile: BuildProfile
    relative_path: str = "."

class BlenderRequest(BaseModel):
    script_path: str = Field(min_length=1, max_length=500)

class RepairRequest(BaseModel):
    relative_path: str = "."
    profile: BuildProfile = "python_compile"
    goal: str = Field(default="Fix the build/test failure with the smallest safe change.", max_length=3000)
    attempts: int | None = None


class ModelGenerationRequest(BaseModel):
    image_ids: list[str] = Field(min_length=1, max_length=4)
    prompt: str = Field(default="", max_length=1000)
    model_type: Literal["single", "multi"] = "single"

class TaskStatusRequest(BaseModel):
    task_type: Literal["image-to-3d", "multi-image-to-3d", "rigging", "animations", "text-to-motion"]
    task_id: str = Field(min_length=8, max_length=100)

class RigRequest(BaseModel):
    model_path: str = Field(min_length=1, max_length=500)
    height_meters: float = Field(default=1.7, gt=0, le=10)

class AnimationRequest(BaseModel):
    rig_task_id: str = Field(min_length=8, max_length=100)
    action_ids: list[int] = Field(default_factory=lambda: [10, 25, 92], min_length=1, max_length=10)
    motion_prompt: str = Field(default="", max_length=1000)

class ApplyMotionRequest(BaseModel):
    rig_task_id: str = Field(min_length=8, max_length=100)
    motion_task_id: str = Field(min_length=8, max_length=100)

class LocalModelRequest(BaseModel):
    model_path: str = Field(min_length=1, max_length=500)

class LocalOptimizeRequest(BaseModel):
    model_path: str = Field(min_length=1, max_length=500)
    target_faces: int = Field(default=50000, ge=1000, le=2000000)
    export_format: Literal['glb','fbx'] = 'glb'

class LocalAnimationRequest(BaseModel):
    model_path: str = Field(min_length=1, max_length=500)
    action: Literal['idle','walk','run','attack','death'] = 'walk'
    fps: int = Field(default=24, ge=12, le=60)


class AgentRunRequest(BaseModel):
    relative_path: str = "."
    task: str = Field(min_length=5, max_length=12000)
    profile: BuildProfile = "python_compile"
    max_steps: int = Field(default=2, ge=1, le=3)
    apply_changes: bool = True


class DetailRecommendationRequest(BaseModel):
    description: str = Field(min_length=3, max_length=4000)

class VisionAnalyzeRequest(BaseModel):
    image_path: str = Field(min_length=1, max_length=500)
    goal: str = Field(default="Create a production-ready 3D asset", max_length=2000)

class IsolatedBuildRequest(BaseModel):
    relative_path: str = "."
    profile: Literal["python_compile","python_tests","node_tests","dotnet_build","cmake_build","unreal_build"] = "python_tests"
    keep_copy: bool = False

class WorktreeCreateRequest(BaseModel):
    relative_path: str = "."
    branch_name: str = Field(default="omniforge-task", min_length=1, max_length=100)

class WorktreePathRequest(BaseModel):
    relative_path: str = Field(min_length=1, max_length=500)
    force: bool = False
