import { Clapperboard, Home, Store, Users, UsersRound } from "lucide-react";
import {
  AiIcon,
  ConstellationsIcon,
  EventsIcon,
  FeedsIcon,
  FriendsIcon,
  GroupsIcon,
  MarketplaceIcon,
  MemoriesIcon,
  MessengerIcon,
  SavedIcon,
  VideoIcon,
} from "./AppIcons";

export const primaryNavigation = [
  { to: "/", label: "Home", icon: Home },
  { to: "/friends", label: "Friends", icon: Users },
  { to: "/watch", label: "Video", icon: Clapperboard },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/groups", label: "Groups", icon: UsersRound },
];

export const sidebarNavigation = [
  { to: "/friends", label: "Friends", icon: FriendsIcon, color: "blue" },
  { to: "/memories", label: "Memories", icon: MemoriesIcon, color: "cyan" },
  { to: "/saved", label: "Saved", icon: SavedIcon, color: "purple" },
  { to: "/groups", label: "Groups", icon: GroupsIcon, color: "blue" },
  {
    to: "/constellations",
    label: "Constellations",
    icon: ConstellationsIcon,
    color: "purple",
  },
  { to: "/watch", label: "Reels", icon: VideoIcon, color: "pink" },
  { to: "/marketplace", label: "Marketplace", icon: MarketplaceIcon, color: "cyan" },
  { to: "/events", label: "Events", icon: EventsIcon, color: "red" },
];

export const extraNavigation = [
  {
    to: "/groups",
    label: "Meta AI Explorers",
    icon: AiIcon,
    color: "purple",
  },
  { to: "/", label: "Feeds", icon: FeedsIcon, color: "blue" },
  { to: "/messages", label: "Messenger", icon: MessengerIcon, color: "blue" },
];
