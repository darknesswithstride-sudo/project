#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Camera/CameraComponent.h"
#include "OFPlayer.generated.h"
UCLASS() class QUALITY_API AOFPlayer:public ACharacter { GENERATED_BODY() public: AOFPlayer(); virtual void Tick(float DeltaSeconds) override; virtual void SetupPlayerInputComponent(UInputComponent*) override; void DamagePlayer(float Amount); void Attack(); void Harvest(); void Build(); void SprintOn(); void SprintOff(); void SaveProgress(); void LoadProgress(); FString HUDText() const; UPROPERTY(VisibleAnywhere) float Health=100; UPROPERTY(VisibleAnywhere) float Stamina=100; UPROPERTY(VisibleAnywhere) int32 Wood=0; UPROPERTY(VisibleAnywhere) int32 Stone=0; UPROPERTY(VisibleAnywhere) UCameraComponent* FirstPersonCamera; private: bool bSprint=false; float AttackWait=0; void Forward(float); void Right(float); };
