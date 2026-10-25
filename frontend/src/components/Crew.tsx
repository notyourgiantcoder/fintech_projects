import type { CrewId, CrewMember } from '../lib/api'

type Size = 'sm' | 'md' | 'lg' | 'xl'

/** A crew member's face: their emoji on a tint of their colour. */
export function Avatar({ member, size = 'md' }: { member?: CrewMember; size?: Size }) {
  if (!member) return <span className={`avatar avatar-${size}`} aria-hidden="true" />
  return (
    <span
      className={`avatar avatar-${size} crew-${member.id}`}
      role="img"
      aria-label={`${member.name} the ${member.animal}`}
    >
      <span aria-hidden="true">{member.emoji}</span>
    </span>
  )
}

export function CrewName({ id, children }: { id: CrewId; children: string }) {
  return <span className={`crew-name crew-${id}`}>{children}</span>
}
