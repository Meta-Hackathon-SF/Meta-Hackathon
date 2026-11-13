import {
  AiIcon,
  EventsIcon,
  FeedsIcon,
  FriendsIcon,
  FriendsTabIcon,
  GamingTabIcon,
  HomeTabIcon,
  MarketplaceTabIcon,
  VideoTabIcon,
  GroupsIcon,
  MarketplaceIcon,
  MemoriesIcon,
  MessengerIcon,
  SavedIcon,
  SpaceIcon,
  SpaceTabIcon,
  VideoIcon,
} from "./AppIcons";
import type { ComponentType } from "react";
import type { TabIconProps } from "./AppIcons";
import type { TabIcon } from "./NavigationIcon";

function asTab(icon: ComponentType<TabIconProps>): TabIcon {
  return Object.assign(icon, { tab: true as const });
}

export const tabIcons = {
  home: asTab(HomeTabIcon),
  friends: asTab(FriendsTabIcon),
  video: asTab(VideoTabIcon),
  marketplace: asTab(MarketplaceTabIcon),
  gaming: asTab(GamingTabIcon),
  space: asTab(SpaceTabIcon),
};

export const primaryNavigation = [
  { to: "/", label: "Home", icon: tabIcons.home },
  { to: "/space", label: "Facebook Space", icon: tabIcons.space },
  { to: "/friends", label: "Friends", icon: tabIcons.friends },
  { to: "/watch", label: "Video", icon: tabIcons.video },
  { to: "/marketplace", label: "Marketplace", icon: tabIcons.marketplace },
  { to: "/gaming", label: "Gaming", icon: tabIcons.gaming },
];

/** Left sidebar, in Facebook's order. Feeds ("/") never shows as active, like Facebook. */
export const sidebarNavigation = [
  { to: "/meta-ai", label: "Meta AI", icon: AiIcon, color: "purple" },
  { to: "/friends", label: "Friends", icon: FriendsIcon, color: "blue" },
  { to: "/memories", label: "Memories", icon: MemoriesIcon, color: "cyan" },
  { to: "/saved", label: "Saved", icon: SavedIcon, color: "purple" },
  { to: "/groups", label: "Groups", icon: GroupsIcon, color: "blue" },
  { to: "/space", label: "Facebook Space", icon: SpaceIcon, color: "purple" },
  { to: "/watch", label: "Reels", icon: VideoIcon, color: "pink" },
  { to: "/marketplace", label: "Marketplace", icon: MarketplaceIcon, color: "cyan" },
  { to: "/", label: "Feeds", icon: FeedsIcon, color: "blue" },
  { to: "/events", label: "Events", icon: EventsIcon, color: "red" },
];

export const extraNavigation = [
  { to: "/groups", label: "Meta AI Explorers", icon: GroupsIcon, color: "purple" },
  { to: "/messages", label: "Messenger", icon: MessengerIcon, color: "blue" },
];
