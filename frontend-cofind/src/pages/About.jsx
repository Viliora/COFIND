import React, { useEffect, useState } from 'react';
import LatestReviewsAside from '../components/LatestReviewsAside';
import anggiPerwitasariPhoto from '../assets/team/anggi-perwitasari.png';
import hengkyAnraPhoto from '../assets/team/hengky-anra.png';
import mohammadAnandaFulviPhoto from '../assets/team/mohammad-ananda-fulvi.png';

const TEAM = [
  {
    name: 'Mohammad Ananda Fulvi',
    title: 'Pengembang',
    bio: 'Merancang dan mengembangkan Cofind sebagai platform rekomendasi coffee shop berbasis ulasan untuk Pontianak.',
    initials: 'MA',
    photo: mohammadAnandaFulviPhoto,
  },
  {
    name: 'Anggi Perwitasari',
    title: 'S. T., M. T.',
    bio: 'Dosen pembimbing yang memberikan arahan akademik dalam perancangan dan pengembangan Cofind.',
    initials: 'AP',
    photo: anggiPerwitasariPhoto,
  },
  {
    name: 'H. Hengky Anra',
    title: 'S. T., M. Kom.',
    bio: 'Dosen pembimbing yang memberikan bimbingan teknis dan akademik selama pengerjaan proyek Cofind.',
    initials: 'HA',
    photo: hengkyAnraPhoto,
  },
];

export default function About() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.title = 'Tentang - Cofind';
    const t = requestAnimationFrame(() => setMounted(true));
    return () => {
      cancelAnimationFrame(t);
      document.title = 'Cofind';
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#FAF9F6] via-stone-50 to-amber-50/30 dark:from-stone-950 dark:via-stone-900 dark:to-stone-800/20 py-6 sm:py-10 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <header
          className={`text-center transition-all duration-500 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
          }`}
        >
          <h1 className="font-serif text-2xl sm:text-3xl md:text-4xl font-bold text-stone-800 dark:text-stone-100 px-2">
            Cofind
          </h1>
        </header>

        <div
          className={`mt-8 sm:mt-10 space-y-10 sm:space-y-12 transition-all duration-500 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
          }`}
        >
          <article className="rounded-2xl border border-stone-200/70 dark:border-stone-700/50 bg-[#FAF9F6]/95 dark:bg-stone-900/70 p-5 sm:p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_280px] gap-6 lg:gap-8 items-start">
              <div className="space-y-5 font-sans text-sm sm:text-base text-stone-700 dark:text-stone-300 leading-relaxed">
                <p>
                  Cofind adalah aplikasi web yang membantu Anda menemukan dan menjelajahi coffee shop di Pontianak. Temukan berbagai tempat melalui katalog dan peta interaktif, lalu dapatkan rekomendasi yang mempertimbangkan lebih dari sekadar angka rating. Cofind memadukan informasi tempat dengan pengalaman yang dibagikan pengunjung melalui ulasan, sehingga Anda dapat menemukan coffee shop yang lebih sesuai dengan kebutuhan dan aktivitas Anda.
                </p>

                <p>
                  Dibangun dari gagasan bahwa coffee shop terbaik bukan selalu yang memiliki rating tertinggi, Cofind membantu menyaring berbagai informasi dari ulasan dan preferensi pengguna untuk menemukan tempat yang benar-benar relevan. Baik untuk belajar, bekerja, bersantai, bertemu teman, maupun berkumpul bersama keluarga. Rekomendasi Cofind dirancang untuk membantu Anda menemukan tempat yang sesuai dengan konteks dan kebutuhan. Setiap rekomendasi juga dilengkapi dengan kutipan ulasan yang relevan, memberikan gambaran nyata mengenai pengalaman pengunjung sebelum Anda berkunjung.
                </p>

                <p>
                  Cofind dapat diakses melalui peramban dan terbuka bagi siapa saja. Pengunjung tanpa akun dapat menjelajahi katalog coffee shop, melihat lokasi melalui peta, serta memperoleh informasi mengenai berbagai tempat. Dengan membuat akun, pengguna dapat menikmati pengalaman yang lebih personal, termasuk mendapatkan rekomendasi berdasarkan preferensi, menulis ulasan, menyimpan coffee shop favorit, dan membuat daftar tempat yang ingin dikunjungi. Penggunaan Cofind tidak memerlukan biaya apa pun, dan selalu tersedia untuk semua pengguna.
                </p>

                <p>
                  Cofind hadir untuk siapa saja yang ingin menemukan coffee shop di Pontianak dengan cara yang lebih bermakna. Mulai dari mahasiswa dan pekerja hingga keluarga, komunitas, dan para penikmat kopi yang selalu mencari tempat baru untuk dikunjungi.
                </p>

                <p>
                  *Note: cofind is solely a coffee shop recommendation website and does not sell coffee.
                </p>
              </div>

              <LatestReviewsAside />
            </div>
          </article>

          <section>
            <h2 className="font-serif text-xl sm:text-2xl font-bold text-stone-800 dark:text-stone-100">
              Cofind Team
            </h2>
            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
              {TEAM.map((member) => (
                <article
                  key={member.name}
                  className="rounded-2xl border border-stone-200/70 dark:border-stone-700/50 bg-[#FAF9F6]/95 dark:bg-stone-900/70 p-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
                >
                  <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-amber-200 to-stone-300 text-lg font-semibold text-stone-700 dark:from-amber-800/50 dark:to-stone-700 dark:text-stone-100">
                    {member.photo ? (
                      <img src={member.photo} alt={member.name} className="h-full w-full object-cover" />
                    ) : (
                      member.initials
                    )}
                  </div>
                  <h3 className="mt-4 font-serif text-lg font-semibold text-stone-800 dark:text-stone-100">
                    {member.name}
                  </h3>
                  <p className="mt-0.5 text-sm font-medium text-amber-800 dark:text-amber-400">
                    {member.title}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-stone-600 dark:text-stone-400">
                    {member.bio}
                  </p>
                </article>
              ))}
            </div>
          </section>
        </div>

        <footer
          className={`mt-12 sm:mt-14 text-center text-xs text-stone-500 dark:text-stone-500 font-sans transition-opacity duration-500 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <p>
            Terima kasih telah menggunakan Cofind — selamat menjelajahi coffee shop
            favorit Anda.
          </p>
        </footer>
      </div>
    </div>
  );
}
