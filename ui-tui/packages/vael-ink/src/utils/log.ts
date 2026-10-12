export function logError(error: unknown): void {
  if (!process.env.VAEL_INK_DEBUG_ERRORS) {
    return
  }

  console.error(error)
}
