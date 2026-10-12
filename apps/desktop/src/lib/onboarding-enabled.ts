export function isOnboardingEnabled(): boolean {
  return window.vaelDesktop?.guestOnboardingEnabled === true
}
