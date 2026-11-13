import type { ComponentType } from "react";
import type { LucideIcon } from "lucide-react";
import type { TabIconProps } from "./AppIcons";

/** A Facebook-style tab icon (outline / filled when active), marked with `tab`. */
export type TabIcon = ComponentType<TabIconProps> & { tab: true };

export default function NavigationIcon({
  icon: Icon,
  active,
  size = 28,
}: {
  icon: LucideIcon | TabIcon;
  label: string;
  active: boolean;
  size?: number;
}) {
  if ("tab" in Icon && Icon.tab) {
    const Tab = Icon as TabIcon;
    return <Tab size={size} active={active} />;
  }
  const Lucide = Icon as LucideIcon;
  return <Lucide aria-hidden="true" size={size - 2} strokeWidth={1.9} />;
}
