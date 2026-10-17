#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "OFGameMode.generated.h"
class ADirectionalLight;
UCLASS() class QUALITY_API AOFGameMode:public AGameModeBase { GENERATED_BODY() public: AOFGameMode(); virtual void BeginPlay()override; virtual void Tick(float DeltaSeconds)override; private: UPROPERTY() ADirectionalLight* SunLight=nullptr; float DayClock=8; float HordeTimer=0; int32 Nights=0; void BuildWorld(); void SpawnHorde(); };
