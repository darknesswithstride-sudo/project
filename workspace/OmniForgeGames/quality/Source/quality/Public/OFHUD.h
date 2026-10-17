#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "OFHUD.generated.h"
UCLASS() class QUALITY_API AOFHUD:public AHUD { GENERATED_BODY() public: virtual void DrawHUD()override; };
