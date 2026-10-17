"""Generate a C++ Unreal Engine 5 zombie-survival vertical-slice project."""
from __future__ import annotations
import json, re, time
from pathlib import Path
from .config import WORKSPACE_DIR
ROOT=(WORKSPACE_DIR/'OmniForgeGames').resolve()
def _slug(name):
 s=re.sub(r'[^A-Za-z0-9_]+','',str(name or 'AshfallSurvival')) or 'AshfallSurvival'
 return ('Game'+s if s[0].isdigit() else s)[:48]
def _put(root, rel, data):
 p=(root/rel).resolve()
 if not p.is_relative_to(root.resolve()): raise ValueError('Generated path escaped project root.')
 p.parent.mkdir(parents=True,exist_ok=True); p.write_text(data,encoding='utf-8'); return p
def generate_unreal_game(project_name='AshfallSurvival', game_brief='', ue_version='5.4'):
 name=_slug(project_name); root=(ROOT/name).resolve()
 if not root.is_relative_to(ROOT): raise ValueError('Invalid project path.')
 if root.exists() and any(root.iterdir()): root=(ROOT/f'{name}_{time.strftime("%Y%m%d_%H%M%S")}').resolve(); name=root.name
 root.mkdir(parents=True,exist_ok=True); api=name.upper()+'_API'; files={}
 files[f'{name}.uproject']=json.dumps({'FileVersion':3,'EngineAssociation':ue_version,'Category':'Games','Description':'OmniForge generated zombie survival prototype','Modules':[{'Name':name,'Type':'Runtime','LoadingPhase':'Default'}]},indent=2)
 files[f'Source/{name}.Target.cs']=f'using UnrealBuildTool;\npublic class {name}Target : TargetRules {{ public {name}Target(TargetInfo Target) : base(Target) {{ Type=TargetType.Game; DefaultBuildSettings=BuildSettingsVersion.V5; ExtraModuleNames.Add("{name}"); }} }}\n'
 files[f'Source/{name}Editor.Target.cs']=f'using UnrealBuildTool;\npublic class {name}EditorTarget : TargetRules {{ public {name}EditorTarget(TargetInfo Target) : base(Target) {{ Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.V5; ExtraModuleNames.Add("{name}"); }} }}\n'
 files[f'Source/{name}/{name}.Build.cs']=f'using UnrealBuildTool;\npublic class {name} : ModuleRules {{ public {name}(ReadOnlyTargetRules Target) : base(Target) {{ PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs; PublicDependencyModuleNames.AddRange(new string[] {{ "Core", "CoreUObject", "Engine", "InputCore", "AIModule", "NavigationSystem", "GameplayTasks" }}); }} }}\n'
 files[f'Source/{name}/{name}.cpp']=f'#include "Modules/ModuleManager.h"\nIMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {name}, "{name}");\n'
 files[f'Source/{name}/Public/OFPlayer.h']=f'''#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Camera/CameraComponent.h"
#include "OFPlayer.generated.h"
UCLASS() class {api} AOFPlayer:public ACharacter {{ GENERATED_BODY() public: AOFPlayer(); virtual void Tick(float DeltaSeconds) override; virtual void SetupPlayerInputComponent(UInputComponent*) override; void DamagePlayer(float Amount); void Attack(); void Harvest(); void Build(); void SprintOn(); void SprintOff(); void SaveProgress(); void LoadProgress(); FString HUDText() const; UPROPERTY(VisibleAnywhere) float Health=100; UPROPERTY(VisibleAnywhere) float Stamina=100; UPROPERTY(VisibleAnywhere) int32 Wood=0; UPROPERTY(VisibleAnywhere) int32 Stone=0; UPROPERTY(VisibleAnywhere) UCameraComponent* FirstPersonCamera; private: bool bSprint=false; float AttackWait=0; void Forward(float); void Right(float); }};
'''
 files[f'Source/{name}/Private/OFPlayer.cpp']=r'''#include "OFPlayer.h"
#include "OFZombie.h"
#include "OFSaveGame.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
AOFPlayer::AOFPlayer(){PrimaryActorTick.bCanEverTick=true;GetCharacterMovement()->MaxWalkSpeed=430;FirstPersonCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));FirstPersonCamera->SetupAttachment(GetCapsuleComponent());FirstPersonCamera->SetRelativeLocation(FVector(0,0,64));FirstPersonCamera->bUsePawnControlRotation=true;}
void AOFPlayer::Tick(float D){Super::Tick(D);AttackWait=FMath::Max(0.f,AttackWait-D);if(bSprint&&Stamina>0){Stamina=FMath::Max(0.f,Stamina-24*D);GetCharacterMovement()->MaxWalkSpeed=640;}else{Stamina=FMath::Min(100.f,Stamina+14*D);GetCharacterMovement()->MaxWalkSpeed=430;if(Stamina<=0)bSprint=false;}}
void AOFPlayer::SetupPlayerInputComponent(UInputComponent* I){Super::SetupPlayerInputComponent(I);I->BindAxis("MoveForward",this,&AOFPlayer::Forward);I->BindAxis("MoveRight",this,&AOFPlayer::Right);I->BindAxis("Turn",this,&APawn::AddControllerYawInput);I->BindAxis("LookUp",this,&APawn::AddControllerPitchInput);I->BindAction("Attack",IE_Pressed,this,&AOFPlayer::Attack);I->BindAction("Harvest",IE_Pressed,this,&AOFPlayer::Harvest);I->BindAction("Build",IE_Pressed,this,&AOFPlayer::Build);I->BindAction("Sprint",IE_Pressed,this,&AOFPlayer::SprintOn);I->BindAction("Sprint",IE_Released,this,&AOFPlayer::SprintOff);I->BindAction("SaveProgress",IE_Pressed,this,&AOFPlayer::SaveProgress);I->BindAction("LoadProgress",IE_Pressed,this,&AOFPlayer::LoadProgress);}
void AOFPlayer::Forward(float V){if(Controller&&V)AddMovementInput(FRotationMatrix(FRotator(0,Controller->GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::X),V);}void AOFPlayer::Right(float V){if(Controller&&V)AddMovementInput(FRotationMatrix(FRotator(0,Controller->GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::Y),V);}
void AOFPlayer::DamagePlayer(float A){Health=FMath::Clamp(Health-A,0.f,100.f);if(Health<=0){Health=100;Wood=FMath::Max(0,Wood-5);SetActorLocation(FVector(0,0,160));}}
void AOFPlayer::Attack(){if(AttackWait>0)return;AttackWait=.55f;FHitResult H;FCollisionQueryParams Q;Q.AddIgnoredActor(this);FVector S=GetActorLocation()+FVector(0,0,40);if(GetWorld()->LineTraceSingleByChannel(H,S,S+GetActorForwardVector()*220,ECC_Pawn,Q)){if(AOFZombie* Z=Cast<AOFZombie>(H.GetActor()))Z->HitZombie(25);}}
void AOFPlayer::Harvest(){TArray<FOverlapResult> H;FCollisionQueryParams Q;Q.AddIgnoredActor(this);if(GetWorld()->OverlapMultiByChannel(H,GetActorLocation()+GetActorForwardVector()*130,FQuat::Identity,ECC_WorldStatic,FCollisionShape::MakeSphere(200),Q)){for(auto& X:H){AActor* A=X.GetActor();if(A&&A->ActorHasTag("OF_Wood")){Wood+=3;A->Destroy();return;}if(A&&A->ActorHasTag("OF_Stone")){Stone+=2;A->Destroy();return;}}}}
void AOFPlayer::Build(){if(Wood<5)return;auto* A=GetWorld()->SpawnActor<AStaticMeshActor>(GetActorLocation()+GetActorForwardVector()*180+FVector(0,0,35),GetActorRotation());if(A){if(auto* M=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")))A->GetStaticMeshComponent()->SetStaticMesh(M);A->SetActorScale3D(FVector(1.5f,.18f,.7f));A->SetActorEnableCollision(true);Wood-=5;}}
void AOFPlayer::SprintOn(){bSprint=true;}void AOFPlayer::SprintOff(){bSprint=false;}
void AOFPlayer::SaveProgress(){USaveGame* Base=UGameplayStatics::CreateSaveGameObject(UOFSaveGame::StaticClass());auto* S=Cast<UOFSaveGame>(Base);if(!S)return;S->Health=Health;S->Stamina=Stamina;S->Wood=Wood;S->Stone=Stone;S->Location=GetActorLocation();UGameplayStatics::SaveGameToSlot(S,TEXT("OmniForgeSlot"),0);}
void AOFPlayer::LoadProgress(){if(!UGameplayStatics::DoesSaveGameExist(TEXT("OmniForgeSlot"),0))return;auto* S=Cast<UOFSaveGame>(UGameplayStatics::LoadGameFromSlot(TEXT("OmniForgeSlot"),0));if(!S)return;Health=FMath::Clamp(S->Health,1.f,100.f);Stamina=FMath::Clamp(S->Stamina,0.f,100.f);Wood=FMath::Max(0,S->Wood);Stone=FMath::Max(0,S->Stone);SetActorLocation(S->Location);}
FString AOFPlayer::HUDText()const{return FString::Printf(TEXT("HEALTH %.0f | STAMINA %.0f | WOOD %d | STONE %d"),Health,Stamina,Wood,Stone);}
'''
 files[f'Source/{name}/Public/OFZombie.h']=f'''#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "OFZombie.generated.h"
UCLASS() class {api} AOFZombie:public ACharacter {{ GENERATED_BODY() public: AOFZombie(); virtual void Tick(float DeltaSeconds)override; void HitZombie(float Damage); UPROPERTY(VisibleAnywhere) float Health=60; private: float BiteCooldown=0; }};
'''
 files[f'Source/{name}/Private/OFZombie.cpp']=r'''#include "OFZombie.h"
#include "OFPlayer.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
AOFZombie::AOFZombie(){PrimaryActorTick.bCanEverTick=true;AutoPossessAI=EAutoPossessAI::PlacedInWorldOrSpawned;GetCharacterMovement()->MaxWalkSpeed=220;UStaticMeshComponent* Visual=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ZombieVisual"));Visual->SetupAttachment(GetCapsuleComponent());Visual->SetRelativeLocation(FVector(0,0,-15));Visual->SetRelativeScale3D(FVector(.65f,.65f,1.25f));if(UStaticMesh* Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")))Visual->SetStaticMesh(Cube);Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);}
void AOFZombie::Tick(float D){Super::Tick(D);BiteCooldown=FMath::Max(0.f,BiteCooldown-D);auto* P=Cast<AOFPlayer>(UGameplayStatics::GetPlayerCharacter(this,0));if(!P)return;float Dist=FVector::Dist(GetActorLocation(),P->GetActorLocation());if(Dist<125&&BiteCooldown<=0){P->DamagePlayer(8);BiteCooldown=1.1f;}else if(Dist<2400){FVector Direction=(P->GetActorLocation()-GetActorLocation());Direction.Z=0;Direction.Normalize();SetActorRotation(Direction.Rotation());AddMovementInput(Direction,1.0f);}}
void AOFZombie::HitZombie(float D){Health-=D;if(Health<=0)Destroy();}
'''
 files[f'Source/{name}/Public/OFSaveGame.h']=f'''#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "OFSaveGame.generated.h"
UCLASS() class {api} UOFSaveGame:public USaveGame {{ GENERATED_BODY() public: UPROPERTY() float Health=100; UPROPERTY() float Stamina=100; UPROPERTY() int32 Wood=0; UPROPERTY() int32 Stone=0; UPROPERTY() FVector Location=FVector(0,0,160); }};
'''
 files[f'Source/{name}/Public/OFGameMode.h']=f'''#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "OFGameMode.generated.h"
class ADirectionalLight;
UCLASS() class {api} AOFGameMode:public AGameModeBase {{ GENERATED_BODY() public: AOFGameMode(); virtual void BeginPlay()override; virtual void Tick(float DeltaSeconds)override; private: UPROPERTY() ADirectionalLight* SunLight=nullptr; float DayClock=8; float HordeTimer=0; int32 Nights=0; void BuildWorld(); void SpawnHorde(); }};
'''
 files[f'Source/{name}/Private/OFGameMode.cpp']=r'''#include "OFGameMode.h"
#include "OFHUD.h"
#include "OFPlayer.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "OFZombie.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Kismet/GameplayStatics.h"
AOFGameMode::AOFGameMode(){DefaultPawnClass=AOFPlayer::StaticClass();HUDClass=AOFHUD::StaticClass();PrimaryActorTick.bCanEverTick=true;}
void AOFGameMode::BeginPlay(){Super::BeginPlay();BuildWorld();}
void AOFGameMode::Tick(float D){Super::Tick(D);DayClock+=D*.035f;if(DayClock>=24)DayClock=0;if(SunLight){float Bright=(DayClock>=19||DayClock<5)?10.0f:100000.0f;SunLight->GetLightComponent()->SetIntensity(Bright);}HordeTimer-=D;if((DayClock>=19||DayClock<5)&&HordeTimer<=0){SpawnHorde();HordeTimer=30;}}
void AOFGameMode::BuildWorld(){auto* W=GetWorld();if(!W)return;SunLight=W->SpawnActor<ADirectionalLight>(FVector(0,0,3000),FRotator(-45,30,0));if(SunLight)SunLight->GetLightComponent()->SetIntensity(100000.0f);auto* Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));auto* Sphere=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere"));if(!Cube)return;for(int X=-10;X<=10;X++)for(int Y=-10;Y<=10;Y++){auto* A=W->SpawnActor<AStaticMeshActor>(FVector(X*450.f,Y*450.f,-70),FRotator::ZeroRotator);if(A){A->GetStaticMeshComponent()->SetStaticMesh(Cube);A->SetActorScale3D(FVector(2.25f,2.25f,.2f));A->SetActorEnableCollision(true);}}for(int I=0;I<100;I++){FVector L(FMath::FRandRange(-4200,4200),FMath::FRandRange(-4200,4200),70);auto* A=W->SpawnActor<AStaticMeshActor>(L,FRotator(0,FMath::FRandRange(0,360),0));if(A){bool Rock=FMath::RandBool();A->GetStaticMeshComponent()->SetStaticMesh(Rock&&Sphere?Sphere:Cube);A->SetActorScale3D(Rock?FVector(1.2f,1.1f,.8f):FVector(.35f,.35f,FMath::FRandRange(1,3)));A->SetActorEnableCollision(true);A->Tags.Add(Rock?"OF_Stone":"OF_Wood");}}for(int I=0;I<14;I++)W->SpawnActor<AOFZombie>(FVector(FMath::FRandRange(-3500,3500),FMath::FRandRange(-3500,3500),100),FRotator::ZeroRotator);}
void AOFGameMode::SpawnHorde(){auto* W=GetWorld();auto* P=Cast<AOFPlayer>(UGameplayStatics::GetPlayerCharacter(this,0));if(!W||!P)return;Nights++;int N=FMath::Clamp(4+Nights*2,4,24);for(int I=0;I<N;I++)W->SpawnActor<AOFZombie>(P->GetActorLocation()+FVector(FMath::FRandRange(-1800,1800),FMath::FRandRange(-1800,1800),100),FRotator::ZeroRotator);}
'''
 files[f'Source/{name}/Public/OFHUD.h']=f'''#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "OFHUD.generated.h"
UCLASS() class {api} AOFHUD:public AHUD {{ GENERATED_BODY() public: virtual void DrawHUD()override; }};
'''
 files[f'Source/{name}/Private/OFHUD.cpp']=r'''#include "OFHUD.h"
#include "OFPlayer.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/Canvas.h"
#include "Engine/CanvasItem.h"
#include "Engine/Engine.h"
void AOFHUD::DrawHUD(){Super::DrawHUD();auto* P=Cast<AOFPlayer>(UGameplayStatics::GetPlayerCharacter(this,0));if(!P||!Canvas)return;FCanvasTextItem A(FVector2D(24,24),FText::FromString(P->HUDText()),GEngine->GetSmallFont(),FLinearColor::White);Canvas->DrawItem(A);FCanvasTextItem B(FVector2D(24,50),FText::FromString(TEXT("WASD move | Mouse look | LMB attack | E harvest | B barricade (5 wood) | Shift sprint | F5 save | F9 load | survive night")),GEngine->GetSmallFont(),FLinearColor(0.7f,0.9f,1,1));Canvas->DrawItem(B);}
'''
 files['Config/DefaultEngine.ini']=f'''[/Script/EngineSettings.GameMapsSettings]\nGlobalDefaultGameMode=/Script/{name}.OFGameMode\n\n[/Script/Engine.InputSettings]\n+AxisMappings=(AxisName="MoveForward",Scale=1.0,Key=W)\n+AxisMappings=(AxisName="MoveForward",Scale=-1.0,Key=S)\n+AxisMappings=(AxisName="MoveRight",Scale=1.0,Key=D)\n+AxisMappings=(AxisName="MoveRight",Scale=-1.0,Key=A)\n+AxisMappings=(AxisName="Turn",Scale=1.0,Key=MouseX)\n+AxisMappings=(AxisName="LookUp",Scale=-1.0,Key=MouseY)\n+ActionMappings=(ActionName="Attack",Key=LeftMouseButton)\n+ActionMappings=(ActionName="Harvest",Key=E)\n+ActionMappings=(ActionName="Build",Key=B)\n+ActionMappings=(ActionName="Sprint",Key=LeftShift)\n+ActionMappings=(ActionName="SaveProgress",Key=F5)\n+ActionMappings=(ActionName="LoadProgress",Key=F9)\n'''
 files['Config/DefaultGame.ini']=f'[/Script/EngineSettings.GeneralProjectSettings]\nProjectName={name}\nProjectVersion=0.1.0\nDescription=OmniForge generated survival game prototype\n'
 files['README_OMNIFORGE.md']=f'''# {name} — OmniForge Unreal survival prototype\n\nBrief: {game_brief or 'Zombie survival'}\n\nGenerated project includes C++ source for player movement/health/stamina, melee combat, harvesting, wood/stone resources, barricade placement, chasing/attacking zombies, runtime-generated primitive terrain/resources, and night horde waves. The HUD and keyboard/mouse input are configured.\n\n## Build on Windows\n1. Install Unreal Engine 5.x through Epic Games Launcher and Visual Studio 2022 with the Game development with C++ workload.\n2. Right-click `{name}.uproject` → Generate Visual Studio project files.\n3. Build the `{name}Editor` Development Editor target, then open the project in Unreal Editor.\n4. The GameMode builds the prototype play area at runtime. Use Platforms → Windows → Package Project to make a Windows build.\n\nControls: WASD move, mouse look, LMB attack, E harvest, B barricade (5 wood), Shift sprint, F5 save player progress, F9 load saved player progress. Save data includes health, stamina, wood, stone, and player location.\n\n## Honest status\nThis is a playable-systems vertical-slice scaffold, not a finished AAA/commercial game. Static project checks can be run without Unreal, but compilation, editor launch, packaging, final art/animation/audio, save/load, multiplayer, level navigation and balance require testing in your local Unreal installation. No Unreal Engine or paid assets are bundled.\n'''
 files['Scripts/Build-Windows.bat']=f'''@echo off\nif "%UE_ROOT%"=="" (echo Set UE_ROOT to your Unreal Engine installation folder first. & exit /b 2)\n"%UE_ROOT%\\Engine\\Build\\BatchFiles\\Build.bat" {name}Editor Win64 Development "%~dp0..\\{name}.uproject" -WaitMutex -FromMsBuild\nif errorlevel 1 exit /b %errorlevel%\necho Build succeeded. Package from Unreal Editor: Platforms ^> Windows ^> Package Project.\npause\n'''
 files['Scripts/Verify-GeneratedProject.py']='''from pathlib import Path\nimport json,sys\nr=Path(__file__).resolve().parents[1]; errors=[]\ntry: d=json.loads((r/(r.name+".uproject")).read_text())\nexcept Exception as e: errors.append(str(e)); d={}\nfor x in ["Config/DefaultEngine.ini","README_OMNIFORGE.md","Source"]:\n if not (r/x).exists(): errors.append("missing "+x)\nfor p in (r/"Source").rglob("*.cpp") if (r/"Source").exists() else []:\n if p.stat().st_size<20: errors.append("empty source "+str(p))\nprint(json.dumps({"project":r.name,"modules":d.get("Modules",[]),"errors":errors,"status":"PASS" if not errors else "FAIL"},indent=2));sys.exit(bool(errors))\n'''
 for rel,content in files.items(): _put(root,rel,content)
 checks={'uproject_json_valid':json.loads((root/f'{name}.uproject').read_text()).get('Modules',[{}])[0].get('Name')==name,'build_module_present':(root/'Source'/name/f'{name}.Build.cs').is_file(),'player_system_present':'void AOFPlayer::Attack' in (root/'Source'/name/'Private/OFPlayer.cpp').read_text(),'zombie_ai_present':'AddMovementInput(Direction,1.0f)' in (root/'Source'/name/'Private/OFZombie.cpp').read_text(),'horde_system_present':'SpawnHorde' in (root/'Source'/name/'Private/OFGameMode.cpp').read_text(),'save_system_present':'SaveGameToSlot' in (root/'Source'/name/'Private/OFPlayer.cpp').read_text() and (root/'Source'/name/'Public/OFSaveGame.h').is_file(),'zombie_chase_present':'AddMovementInput(Direction,1.0f)' in (root/'Source'/name/'Private/OFZombie.cpp').read_text(),'input_config_present':'ActionName="Harvest"' in (root/'Config/DefaultEngine.ini').read_text() and 'ActionName="SaveProgress"' in (root/'Config/DefaultEngine.ini').read_text()}
 manifest={'project_name':name,'engine_association':ue_version,'generated_at':time.time(),'requested_brief':game_brief,'file_count':len(files),'checks':checks,'static_validation_passed':all(checks.values()),'status':'GENERATED' if all(checks.values()) else 'GENERATED_WITH_WARNINGS','project_path':str(root),'uproject_path':str(root/f'{name}.uproject'),'readme_path':str(root/'README_OMNIFORGE.md'),'build_verified':False,'note':'Unreal compiler/editor was not run by OmniForge here. Use local Unreal Engine to compile and package.'}
 _put(root,'OmniForgeGameManifest.json',json.dumps(manifest,indent=2)); return manifest
def inspect_unreal_installation():
 import os
 from .config import UNREAL_BUILD_TOOL
 candidates=[UNREAL_BUILD_TOOL] if UNREAL_BUILD_TOOL else []
 candidates += [os.getenv(k,'') for k in ('UE_ROOT','UNREAL_ENGINE_ROOT')]
 found=[p for p in candidates if p and Path(p).exists()]
 return {'status':'SUCCEEDED','configured_build_tool':UNREAL_BUILD_TOOL or None,'detected_paths':found,'build_tool_available':bool(found),'note':'Actual compile status is only reported after invoking the local Unreal build tool.'}


async def build_and_repair_generated_game(manifest: dict, max_repair_attempts: int = 1) -> dict:
    """Compile a generated project when Unreal is configured; try one bounded AI repair on failure.

    Static generation is never reported as a successful Unreal build. If the engine is missing,
    the result explicitly stays in generated-but-uncompiled state.
    """
    import asyncio
    from .config import WORKSPACE_DIR, UNREAL_BUILD_TOOL
    result = dict(manifest)
    result.setdefault('build_attempts', [])
    if not result.get('static_validation_passed'):
        result.update(build_verified=False, build_status='BLOCKED_STATIC_VALIDATION')
        return result
    if not UNREAL_BUILD_TOOL:
        result.update(build_verified=False, build_status='ENGINE_OR_BUILD_TOOL_NOT_CONFIGURED',
                      warning='Project files were generated and statically checked, but Unreal Engine compilation was not run because UNREAL_BUILD_TOOL is not configured.')
        return result
    project = Path(str(result.get('project_path', ''))).resolve()
    workspace = WORKSPACE_DIR.resolve()
    if not project.is_relative_to(workspace):
        result.update(build_verified=False, build_status='BLOCKED_PATH_VALIDATION',
                      warning='Generated project is outside the configured workspace; refusing to invoke the build tool.')
        return result
    relative = project.relative_to(workspace).as_posix()
    # When a local compiler is available, first let the local coding agent implement the
    # user's game-specific requirements on top of the tested baseline. It is constrained to
    # this generated project and must use the Unreal build profile as its verifier.
    brief = str(result.get('requested_brief') or '').strip()
    if brief:
        try:
            from .coding_engine import run_coding_agent
            feature_pass = await run_coding_agent(relative,
                "Expand this generated Unreal Engine project toward the user requested game. "
                'Read the existing source before editing. Implement the highest-priority missing requirements from the brief below, '
                'preserve existing working systems, keep all file changes inside this project, use built-in engine assets only, '
                'and do not claim bespoke art or unsupported systems exist. Run the Unreal build verifier and make a bounded repair if needed.\n'
                'USER GAME BRIEF:\n' + brief[:5000], 'unreal_build', 2, True)
            result.setdefault('build_attempts', []).append({'attempt': 0, 'kind': 'brief_driven_feature_pass', 'result': feature_pass})
        except Exception as exc:
            result.setdefault('build_attempts', []).append({'attempt': 0, 'kind': 'brief_driven_feature_pass', 'error': str(exc)[:2000]})
    from .build_runner import run_profile
    try:
        first = await asyncio.to_thread(run_profile, 'unreal_build', relative)
    except Exception as exc:
        first = {'ok': False, 'error': str(exc), 'exit_code': -1}
    result['build_attempts'].append({'attempt': 1, 'kind': 'initial_build', 'result': first})
    if isinstance(first, dict) and first.get('ok') is True:
        result.update(build_verified=True, build_status='COMPILED')
        return result
    if max_repair_attempts > 0:
        try:
            from .coding_engine import run_coding_agent
            evidence = json.dumps(first, ensure_ascii=False)[:10000]
            repair = await run_coding_agent(relative,
                'Repair this generated Unreal C++ project so it compiles. Keep changes limited to this generated project. '
                'Use the following compiler/build evidence, make the smallest targeted fix, and verify with the Unreal build profile. '
                'Do not replace gameplay systems with placeholders.\nBUILD EVIDENCE: ' + evidence,
                'unreal_build', 2, True)
            result['build_attempts'].append({'attempt': 2, 'kind': 'targeted_ai_repair', 'result': repair})
            try:
                second = await asyncio.to_thread(run_profile, 'unreal_build', relative)
            except Exception as exc:
                second = {'ok': False, 'error': str(exc), 'exit_code': -1}
            result['build_attempts'].append({'attempt': 3, 'kind': 'verification_build', 'result': second})
            if isinstance(second, dict) and second.get('ok') is True:
                result.update(build_verified=True, build_status='COMPILED_AFTER_REPAIR')
                return result
            result.update(build_verified=False, build_status='BUILD_FAILED_AFTER_REPAIR',
                          warning='The generated project failed its initial Unreal build and the bounded repair did not verify a fix.')
            return result
        except Exception as exc:
            result['build_attempts'].append({'attempt': 2, 'kind': 'targeted_ai_repair', 'error': str(exc)[:2000]})
    result.update(build_verified=False, build_status='BUILD_FAILED',
                  warning='Unreal build failed. See build_attempts for compiler output and recovery details.')
    return result
