import { Link } from "react-router";
import type { Author } from "../../types/feed";

export default function Avatar({
  person,
  size = 40,
  online = false,
  link = false,
}: {
  person: Author;
  size?: number;
  online?: boolean;
  link?: boolean;
}) {
  const avatar = (
    <span
      className={`avatar${online ? " is-online" : ""}`}
      style={{ width: size, height: size }}
    >
      <img src={person.avatar} alt={person.name} width={size} height={size} />
    </span>
  );
  return link ? (
    <Link to="/profile" aria-label={`${person.name}'s profile`}>
      {avatar}
    </Link>
  ) : (
    avatar
  );
}
