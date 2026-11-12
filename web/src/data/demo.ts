import type { Author, Post } from "../types/feed";

export const photo = (name: string) => `/demo/${name}.jpg`;
export const currentUser: Author = {
  name: "Alex Morgan",
  avatar: photo("avatar-alex"),
};
export const people: Author[] = [
  { name: "Maya Chen", avatar: photo("avatar-maya") },
  { name: "Jordan Davis", avatar: photo("avatar-jordan") },
  { name: "Sofia Patel", avatar: photo("avatar-sofia") },
  { name: "Daniel Kim", avatar: photo("avatar-daniel") },
  { name: "Emma Wilson", avatar: photo("avatar-emma") },
  { name: "Alex Morgan", avatar: photo("avatar-alex") },
];

export const stories = [
  {
    author: people[0],
    image: photo("campus"),
    caption: "A little campus magic",
  },
  {
    author: people[1],
    image: photo("workspace"),
    caption: "Building something good",
  },
  { author: people[2], image: photo("coast"), caption: "Weekend reset" },
  { author: people[4], image: photo("coffee"), caption: "One more coffee ☕" },
  { author: people[3], image: photo("headset"), caption: "A whole new world" },
];

export const initialPosts: Post[] = [
  {
    id: "hackathon",
    author: { ...people[0], community: "Hackathon Builders Community" },
    timestamp: "22m",
    visibility: "Public",
    text: "Different campuses. One big idea. 💙 Getting ready for the Meta Closer Together with AI Hackathon! Who else is joining?",
    images: [
      {
        src: photo("team"),
        alt: "A group of students collaborating around a table",
      },
    ],
    reactionCount: 128,
    commentCount: 24,
    shareCount: 8,
  },
  {
    id: "campus-walk",
    author: people[1],
    timestamp: "1h",
    visibility: "Friends",
    text: "Different paths, shared memories. Here’s to all the people who made campus feel like home. 🎓",
    images: [
      { src: photo("campus"), alt: "Graduates celebrating together outdoors" },
    ],
    reactionCount: 86,
    commentCount: 12,
    shareCount: 2,
  },
  {
    id: "ai-builders",
    author: {
      ...people[2],
      community: "Meta AI Explorers · student community",
    },
    timestamp: "2h",
    visibility: "Public",
    text: "A small win from our AI study group: we made our first Llama-powered prototype work! 🎉\n\nThe best part wasn’t the code. It was watching everyone bring a different perspective to the problem. One teammate studies design, another studies linguistics, and two of us are in CS.\n\nWe’re experimenting with ways to make campus information easier to find, starting with club events and study spaces. There’s still a lot to learn about evaluation, privacy, and accessibility, but we’re excited about the direction.\n\nIf you’re learning too, drop a resource that helped you get started. Let’s build together.",
    reactionCount: 214,
    commentCount: 37,
    shareCount: 15,
  },
  {
    id: "design-night",
    author: { ...people[4], community: "Campus Creatives" },
    timestamp: "3h",
    visibility: "Public",
    text: "Good people, very questionable sketches, and a lot of big ideas. A few moments from our design jam last night ✨",
    images: [
      {
        src: photo("workspace"),
        alt: "A busy creative workshop with laptops and notebooks",
      },
      { src: photo("code"), alt: "A laptop and notebook on a designer’s desk" },
      {
        src: photo("coffee"),
        alt: "A cup of coffee during a late-night work session",
      },
    ],
    reactionCount: 72,
    commentCount: 9,
    shareCount: 3,
  },
  {
    id: "vr-club",
    author: { ...people[3], community: "XR Student Collective" },
    timestamp: "4h",
    visibility: "Public",
    text: "First time trying a shared space in VR and I completely forgot we were on different campuses. Anyone up for a little AR/VR demo night?",
    images: [
      {
        src: photo("headset"),
        alt: "An immersive virtual reality headset demonstration",
      },
    ],
    reactionCount: 156,
    commentCount: 28,
    shareCount: 11,
  },
  {
    id: "study-group",
    author: people[0],
    timestamp: "5h",
    visibility: "Friends",
    text: "Looking for two more people for a Sunday study session at the library. Bring your hardest bug and your favorite snack. I’ll bring the coffee. ☕",
    reactionCount: 31,
    commentCount: 18,
    shareCount: 0,
  },
  {
    id: "demo-day",
    author: { ...people[1], community: "Hackathon Builders Community" },
    timestamp: "6h",
    visibility: "Public",
    text: "A little practice before the big pitch! Come share what you’re building, try someone else’s prototype, or just meet a few new people.",
    event: {
      day: "14",
      month: "NOV",
      title: "Build together: community demo night",
      location: "Student Innovation Lab · 6:00 PM",
    },
    reactionCount: 95,
    commentCount: 14,
    shareCount: 22,
  },
  {
    id: "coast",
    author: people[2],
    timestamp: "7h",
    visibility: "Friends",
    text: "Our hiking club has a very loose definition of “a quick walk.” Worth every step though. 🌊",
    images: [
      {
        src: photo("coast"),
        alt: "Ocean waves meeting the shore on a sunny afternoon",
      },
    ],
    reactionCount: 183,
    commentCount: 16,
    shareCount: 4,
  },
  {
    id: "open-source",
    author: people[3],
    timestamp: "8h",
    visibility: "Public",
    text: "My first open source contribution was one line of documentation. My second was fixing the typo I introduced in that line. Progress is progress 😅\n\nIf you’re nervous about getting started, this is your sign.",
    reactionCount: 302,
    commentCount: 41,
    shareCount: 19,
  },
  {
    id: "music-night",
    author: { ...people[4], community: "After Class · campus community" },
    timestamp: "9h",
    visibility: "Public",
    text: "Nothing brings strangers together quite like knowing every word to the same song. Best campus night in a while 🎶",
    images: [
      {
        src: photo("concert"),
        alt: "Friends enjoying an outdoor live music event",
      },
    ],
    reactionCount: 241,
    commentCount: 32,
    shareCount: 9,
  },
  {
    id: "library",
    author: people[0],
    timestamp: "12h",
    visibility: "Friends",
    text: "Found my new favorite corner of campus. Quiet enough to think, close enough to the café. 📚",
    images: [
      {
        src: photo("library"),
        alt: "Warmly lit bookshelves in a university library",
      },
      { src: photo("coffee"), alt: "Fresh coffee on a café table" },
    ],
    reactionCount: 64,
    commentCount: 8,
    shareCount: 1,
  },
  {
    id: "community",
    author: {
      ...people[2],
      community: "Technology for Good · student community",
    },
    timestamp: "16h",
    visibility: "Public",
    text: "A reminder for anyone building at the hackathon: the most useful feature might be the simplest one.\n\nAsk someone what makes it hard to connect with their community. Listen before you open your editor. Build with them. Then ask again. 💙",
    reactionCount: 178,
    commentCount: 22,
    shareCount: 35,
  },
  {
    id: "desk-cat",
    author: currentUser,
    timestamp: "Yesterday",
    visibility: "Friends",
    text: "Our newest teammate has very strong opinions about keyboard shortcuts. Productivity is down. Morale is way up. 🐈",
    images: [
      {
        src: photo("cat"),
        alt: "A curious cat taking a break from supervising the team",
      },
    ],
    reactionCount: 92,
    commentCount: 17,
    shareCount: 3,
  },
  {
    id: "late-night",
    author: people[1],
    timestamp: "Yesterday",
    visibility: "Friends",
    text: "Closed 12 tabs. Opened 14 more. Calling that a productive evening.\n\nSee you at the next build session!",
    images: [
      {
        src: photo("code"),
        alt: "A laptop ready for another evening of building",
      },
    ],
    reactionCount: 47,
    commentCount: 6,
    shareCount: 0,
  },
];

export const notifications = [
  {
    id: "n1",
    person: people[0],
    text: "Maya Chen and 12 others liked your post.",
    time: "2m",
    to: "/profile",
    unread: true,
  },
  {
    id: "n2",
    person: people[1],
    text: "Jordan Davis commented: “Can’t wait to see what you build!”",
    time: "18m",
    to: "/",
    unread: true,
  },
  {
    id: "n3",
    person: people[2],
    text: "Sofia Patel invited you to Build together: community demo night.",
    time: "1h",
    to: "/events",
    unread: true,
  },
  {
    id: "n4",
    person: people[4],
    text: "Emma Wilson added a new photo in Campus Creatives.",
    time: "3h",
    to: "/groups",
    unread: false,
  },
];
