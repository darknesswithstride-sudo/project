#include "OFGameMode.h"
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
