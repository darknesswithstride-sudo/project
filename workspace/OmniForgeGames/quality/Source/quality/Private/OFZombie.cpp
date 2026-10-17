#include "OFZombie.h"
#include "OFPlayer.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
AOFZombie::AOFZombie(){PrimaryActorTick.bCanEverTick=true;AutoPossessAI=EAutoPossessAI::PlacedInWorldOrSpawned;GetCharacterMovement()->MaxWalkSpeed=220;UStaticMeshComponent* Visual=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ZombieVisual"));Visual->SetupAttachment(GetCapsuleComponent());Visual->SetRelativeLocation(FVector(0,0,-15));Visual->SetRelativeScale3D(FVector(.65f,.65f,1.25f));if(UStaticMesh* Cube=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")))Visual->SetStaticMesh(Cube);Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);}
void AOFZombie::Tick(float D){Super::Tick(D);BiteCooldown=FMath::Max(0.f,BiteCooldown-D);auto* P=Cast<AOFPlayer>(UGameplayStatics::GetPlayerCharacter(this,0));if(!P)return;float Dist=FVector::Dist(GetActorLocation(),P->GetActorLocation());if(Dist<125&&BiteCooldown<=0){P->DamagePlayer(8);BiteCooldown=1.1f;}else if(Dist<2400){FVector Direction=(P->GetActorLocation()-GetActorLocation());Direction.Z=0;Direction.Normalize();SetActorRotation(Direction.Rotation());AddMovementInput(Direction,1.0f);}}
void AOFZombie::HitZombie(float D){Health-=D;if(Health<=0)Destroy();}
