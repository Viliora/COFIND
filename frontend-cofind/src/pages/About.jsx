import React from 'react';

const About = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-zinc-900 py-6 sm:py-8 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <div className="text-center py-8 sm:py-12 md:py-16">
          <svg
            className="mx-auto h-16 w-16 sm:h-20 sm:w-20 md:h-24 md:w-24 text-blue-400 dark:text-blue-500"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.5"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <h1 className="mt-4 sm:mt-6 text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 dark:text-white px-4">
            Tentang Cofind
          </h1>
          <div className="mt-6 sm:mt-8 text-left space-y-3 sm:space-y-4 text-gray-600 dark:text-gray-300 px-4">
            <p className="text-base sm:text-lg">
              Cofind adalah aplikasi untuk menemukan coffee shop terbaik di sekitar Anda.
            </p>
            <p className="text-sm sm:text-base">
              Aplikasi ini membantu Anda menemukan tempat ngopi yang sesuai dengan preferensi dan kebutuhan Anda.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default About;

