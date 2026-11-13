import { Gamepad2, Home, MonitorPlay, Store, Users } from "lucide-react";
import {
  AiIcon,
  EventsIcon,
  FeedsIcon,
  FriendsIcon,
  GroupsIcon,
  MarketplaceIcon,
  MemoriesIcon,
  MessengerIcon,
  SavedIcon,
  SpaceIcon,
  VideoIcon,
} from "./AppIcons";

export const primaryNavigation = [
  { to: "/", label: "Home", icon: Home },
  { to: "/friends", label: "Friends", icon: Users },
  { to: "/watch", label: "Video", icon: MonitorPlay },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/gaming", label: "Gaming", icon: Gamepad2 },
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
