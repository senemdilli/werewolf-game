let clockOffset = 0;

export function setClockOffset(offset: number) {
  clockOffset = offset;
}

export function safeDateNow(): number {
  return Date.now() + clockOffset;
}
