import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ChatProvider } from './contexts/ChatContext';
import MainLayout from './layouts/MainLayout';
import ChatPage from './pages/ChatPage';
import MistakesPage from './pages/MistakesPage';
import ExercisesPage from './pages/ExercisesPage';
import BooksPage from './pages/BooksPage';
import LearningPage from './pages/LearningPage';
import WeeklyReportPage from './pages/WeeklyReportPage';
import DesktopTitleBar from './components/DesktopTitleBar';
import FirstRunGuide from './components/FirstRunGuide';

function App() {
  return (
    <ChatProvider>
      <DesktopTitleBar />
      <FirstRunGuide />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<ChatPage />} />
            <Route path="mistakes" element={<MistakesPage />} />
            <Route path="exercises" element={<ExercisesPage />} />
            <Route path="kg" element={<Navigate to="/learning" replace />} />
            <Route path="learning" element={<LearningPage />} />
            <Route path="weekly" element={<WeeklyReportPage />} />
            <Route path="books" element={<BooksPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ChatProvider>
  );
}

export default App;
