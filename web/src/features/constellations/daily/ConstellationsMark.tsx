import { SpaceIcon } from "../../../components/navigation/AppIcons";

/** Facebook Space badge: the same logo as the left sidebar. */
export default function ConstellationsMark({ size = 40 }: { size?: number }) {
  return (
    <span className="cst-mark is-logo" style={{ width: size, height: size }} aria-hidden="true">
      <SpaceIcon size={size} />
    </span>
  );
}
