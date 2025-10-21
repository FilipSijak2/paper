import type { FC } from 'react';
import './Navbar.css';

export type Section = 'entry' | 'simple' | '3d';

interface NavbarProps {
  currentSection: Section;
  setCurrentSection: (section: Section) => void;
}

const Navbar: FC<NavbarProps> = ({ currentSection, setCurrentSection }) => {
  const sections: { id: Section; label: string }[] = [
    { id: 'entry', label: 'Entry' },
    { id: 'simple', label: 'Simple Control' },
    { id: '3d', label: '3D View' },
  ];
  return (
    <nav className="navbar">
      <ul className="navbar-list">
        {sections.map(section => (
          <li
            key={section.id}
            className={`navbar-item ${currentSection === section.id ? 'active' : ''}`}
            onClick={() => setCurrentSection(section.id)}
          >
            {section.label}
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navbar;
