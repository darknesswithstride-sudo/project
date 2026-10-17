#include "OFHUD.h"
#include "OFPlayer.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/Canvas.h"
#include "Engine/CanvasItem.h"
#include "Engine/Engine.h"
void AOFHUD::DrawHUD(){Super::DrawHUD();auto* P=Cast<AOFPlayer>(UGameplayStatics::GetPlayerCharacter(this,0));if(!P||!Canvas)return;FCanvasTextItem A(FVector2D(24,24),FText::FromString(P->HUDText()),GEngine->GetSmallFont(),FLinearColor::White);Canvas->DrawItem(A);FCanvasTextItem B(FVector2D(24,50),FText::FromString(TEXT("WASD move | Mouse look | LMB attack | E harvest | B barricade (5 wood) | Shift sprint | F5 save | F9 load | survive night")),GEngine->GetSmallFont(),FLinearColor(0.7f,0.9f,1,1));Canvas->DrawItem(B);}
