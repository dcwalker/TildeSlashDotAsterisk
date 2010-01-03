require 'rubygems'
require 'rake'

desc "symlink all config files, prepending a period (bashrc becomes .bashrc)"
task :symlink do
  config_dir = File.dirname(__FILE__)
  (Dir.glob('*') - ['.', '..','.git','Rakefile']).each do |config_file|
    ln_s "#{File.join(config_dir, config_file)}", "#{ENV['HOME']}/.#{config_file}"
  end
end