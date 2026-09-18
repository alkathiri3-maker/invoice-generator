import { Link } from 'react-router-dom';

const TemplatesPage = () => {
  return (
    <div>
      <Link 
        to="/visual-editor"
        className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 inline-block"
      >
        محرر مرئي
      </Link>
    </div>
  );
};