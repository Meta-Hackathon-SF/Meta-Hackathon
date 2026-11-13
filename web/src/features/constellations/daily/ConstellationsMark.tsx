import { SpaceIcon } from "../../../components/navigation/AppIcons";

/** Use the sidebar's exact Space icon, including its color and proportions. */
export default function ConstellationsMark({ size = 40 }: { size?: number }) {
  return (
    <span className="cst-mark nav-color-purple" style={{ width: size, height: size }} aria-hidden="true">
      <SpaceIcon size={size} />
    </span>
  );
}
