import { useState } from 'react';

// Search
import { FaSearch } from 'react-icons/fa';
import { HiSearch } from 'react-icons/hi';
import { HiMagnifyingGlass } from 'react-icons/hi2';
import { LuSearch } from 'react-icons/lu';
import { RiSearchLine } from 'react-icons/ri';
import { IoSearchOutline, IoSearch } from 'react-icons/io5';
import { MdSearch, MdOutlineSearch } from 'react-icons/md';
import { TbSearch } from 'react-icons/tb';

// Bell
import { FaBell, FaRegBell } from 'react-icons/fa';
import { HiBell as HiBellV1 } from 'react-icons/hi';
import { HiBell as HiBellV2 } from 'react-icons/hi2';
import { LuBell } from 'react-icons/lu';
import { RiBellLine, RiBellFill } from 'react-icons/ri';
import { IoBellOutline, IoBell } from 'react-icons/io5';
import { MdNotificationsNone, MdNotifications } from 'react-icons/md';
import { TbBell } from 'react-icons/tb';

// Hamburger / menu
import { FaBars } from 'react-icons/fa';
import { HiMenu } from 'react-icons/hi';
import { HiBars3 } from 'react-icons/hi2';
import { LuMenu } from 'react-icons/lu';
import { RiMenuLine } from 'react-icons/ri';
import { IoMenuOutline, IoMenu } from 'react-icons/io5';
import { MdMenu } from 'react-icons/md';
import { TbMenu2 } from 'react-icons/tb';

const SEARCH_OPTIONS = [
  { label: 'FA solid (FaSearch)',                 Icon: FaSearch },
  { label: 'Heroicons v1 sw=2 (HiSearch)',        Icon: HiSearch },
  { label: 'Heroicons v2 sw=1.5 (HiMagnifyingGlass)', Icon: HiMagnifyingGlass },
  { label: 'Lucide (LuSearch)',                   Icon: LuSearch },
  { label: 'Remix outline (RiSearchLine)',        Icon: RiSearchLine },
  { label: 'Ionicons outline (IoSearchOutline)',  Icon: IoSearchOutline },
  { label: 'Ionicons solid (IoSearch)',           Icon: IoSearch },
  { label: 'Material filled (MdSearch)',          Icon: MdSearch },
  { label: 'Material outline (MdOutlineSearch)',  Icon: MdOutlineSearch },
  { label: 'Tabler (TbSearch)',                   Icon: TbSearch },
];

const BELL_OPTIONS = [
  { label: 'FA solid (FaBell)',                   Icon: FaBell },
  { label: 'FA regular/outline (FaRegBell)',      Icon: FaRegBell },
  { label: 'Heroicons v1 sw=2 (HiBellV1)',        Icon: HiBellV1 },
  { label: 'Heroicons v2 sw=1.5 (HiBellV2)',      Icon: HiBellV2 },
  { label: 'Lucide (LuBell)',                     Icon: LuBell },
  { label: 'Remix outline (RiBellLine)',          Icon: RiBellLine },
  { label: 'Remix fill (RiBellFill)',             Icon: RiBellFill },
  { label: 'Ionicons outline (IoBellOutline)',    Icon: IoBellOutline },
  { label: 'Ionicons solid (IoBell)',             Icon: IoBell },
  { label: 'Material outline (MdNotificationsNone)', Icon: MdNotificationsNone },
  { label: 'Material filled (MdNotifications)',   Icon: MdNotifications },
  { label: 'Tabler (TbBell)',                     Icon: TbBell },
];

const MENU_OPTIONS = [
  { label: 'FA solid (FaBars)',                   Icon: FaBars },
  { label: 'Heroicons v1 sw=2 (HiMenu)',          Icon: HiMenu },
  { label: 'Heroicons v2 sw=1.5 (HiBars3)',       Icon: HiBars3 },
  { label: 'Lucide (LuMenu)',                     Icon: LuMenu },
  { label: 'Remix outline (RiMenuLine)',          Icon: RiMenuLine },
  { label: 'Ionicons outline (IoMenuOutline)',    Icon: IoMenuOutline },
  { label: 'Ionicons solid (IoMenu)',             Icon: IoMenu },
  { label: 'Material (MdMenu)',                   Icon: MdMenu },
  { label: 'Tabler (TbMenu2)',                    Icon: TbMenu2 },
];

const SIZES = [14, 16, 18, 20, 22, 24];

function IconColumn({ label, options, selectedIndex, onChange, size }) {
  const { Icon } = options[selectedIndex];
  return (
    <div className="flex flex-col items-center gap-6">
      <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">{label}</p>
      <div className="w-24 h-24 rounded-2xl bg-gray-100 flex items-center justify-center">
        <Icon style={{ width: size, height: size }} className="text-gray-600" />
      </div>
      <select
        value={selectedIndex}
        onChange={e => onChange(Number(e.target.value))}
        className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-300 w-56"
      >
        {options.map((opt, i) => (
          <option key={i} value={i}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
}

export default function IconPicker() {
  const [searchIdx, setSearchIdx] = useState(0);
  const [bellIdx, setBellIdx] = useState(0);
  const [menuIdx, setMenuIdx] = useState(0);
  const [size, setSize] = useState(20);

  const SearchIcon = SEARCH_OPTIONS[searchIdx].Icon;
  const BellIcon   = BELL_OPTIONS[bellIdx].Icon;
  const MenuIcon   = MENU_OPTIONS[menuIdx].Icon;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-16 px-4">

      {/* Size picker */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-400">Size</span>
        <div className="flex gap-1">
          {SIZES.map(s => (
            <button
              key={s}
              onClick={() => setSize(s)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                size === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-100'
              }`}
            >
              {s}px
            </button>
          ))}
        </div>
      </div>

      {/* Individual pickers */}
      <div className="flex flex-wrap gap-16 justify-center">
        <IconColumn label="Search"    options={SEARCH_OPTIONS} selectedIndex={searchIdx} onChange={setSearchIdx} size={size} />
        <IconColumn label="Bell"      options={BELL_OPTIONS}   selectedIndex={bellIdx}   onChange={setBellIdx}   size={size} />
        <IconColumn label="Hamburger" options={MENU_OPTIONS}   selectedIndex={menuIdx}   onChange={setMenuIdx}   size={size} />
      </div>

      {/* Combined preview */}
      <div className="flex flex-col items-center gap-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">Preview together</p>
        <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-xl px-3 py-2 shadow-sm">
          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
            <SearchIcon style={{ width: size, height: size }} />
          </button>
          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
            <BellIcon style={{ width: size, height: size }} />
          </button>
          <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
            <MenuIcon style={{ width: size, height: size }} />
          </button>
        </div>
        <p className="text-xs text-gray-400">
          {SEARCH_OPTIONS[searchIdx].label.split('(')[0].trim()} ·{' '}
          {BELL_OPTIONS[bellIdx].label.split('(')[0].trim()} ·{' '}
          {MENU_OPTIONS[menuIdx].label.split('(')[0].trim()}
        </p>
      </div>

    </div>
  );
}
